import http from "http";
import crypto from "crypto";
import { spawn } from "child_process";
import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import { WebSocket, WebSocketServer } from "ws";
import path from "path";
import readline from "readline";

dotenv.config();

const PORT = process.env.PORT ? Number(process.env.PORT) : 8787;
const HOST = process.env.HOST || "127.0.0.1";
const FRONTEND_ORIGIN = process.env.FRONTEND_ORIGIN || "http://localhost:5173";
const MAX_CONNECTIONS_PER_IP = 5;
const NATIVE_TYPE_ENABLED = process.env.NATIVE_TYPE_ENABLED === "true";
const NATIVE_TYPE_CMD = process.env.NATIVE_TYPE_CMD || "xdotool";

const PYTHON_VENV_PATH = path.join(process.cwd(), ".venv", "bin", "python3");
const TRANSCRIBE_SCRIPT = path.join(process.cwd(), "scripts", "transcribe.py");
const HOTKEY_SCRIPT = path.join(process.cwd(), "scripts", "hotkey.py");

const connectionsByIP = new Map();

const app = express();
app.set("trust proxy", true);
app.use(express.json());
app.use(
  cors({
    origin: FRONTEND_ORIGIN,
    methods: ["GET", "POST"],
    credentials: true
  })
);

app.get("/health", (_req, res) => {
  res.json({ ok: true });
});

app.post("/api/native/type", (req, res) => {
  if (!NATIVE_TYPE_ENABLED) {
    res.status(400).json({ error: "Native typing disabled. Set NATIVE_TYPE_ENABLED=true" });
    return;
  }
  if (process.platform !== "linux") {
    res.status(400).json({ error: "Native typing only supported on Linux" });
    return;
  }
  const {
    text = "",
    appendSpace = true,
    backspaces = 0,
    delayMs = 1
  } = req.body || {};
  const normalizedBackspaces = Number.isFinite(backspaces)
    ? Math.max(0, Math.min(2000, Math.floor(backspaces)))
    : 0;
  const normalizedDelayMs = Number.isFinite(delayMs)
    ? Math.max(0, Math.min(25, Math.floor(delayMs)))
    : 1;

  if (typeof text !== "string") {
    res.status(400).json({ error: "Missing text" });
    return;
  }
  if (text.length > 2000) {
    res.status(400).json({ error: "Text too long" });
    return;
  }
  if (text.trim().length === 0 && normalizedBackspaces === 0) {
    res.status(400).json({ error: "Missing text" });
    return;
  }

  const finalText = text.length > 0
    ? (appendSpace ? `${text} ` : text)
    : "";
  const args = [];
  if (normalizedBackspaces > 0) {
    args.push("key", "--clearmodifiers", "--repeat", String(normalizedBackspaces), "BackSpace");
  }
  if (finalText.length > 0) {
    args.push("type", "--clearmodifiers", "--delay", String(normalizedDelayMs), "--", finalText);
  }
  if (args.length === 0) {
    res.json({ ok: true });
    return;
  }

  const child = spawn(NATIVE_TYPE_CMD, args, { stdio: "ignore" });

  let responded = false;
  child.on("error", (err) => {
    if (responded) return;
    responded = true;
    res.status(500).json({ error: err.message || "Failed to run native typing command" });
  });

  child.on("exit", (code) => {
    if (responded) return;
    responded = true;
    if (code === 0) {
      res.json({ ok: true });
    } else {
      res.status(500).json({ error: `Native typing exited with code ${code}` });
    }
  });
});

app.post("/api/realtime/session", (req, res) => {
  const protocol = req.headers["x-forwarded-proto"] || req.protocol || "http";
  const wsProtocol = protocol === "https" ? "wss" : "ws";
  const sessionId = crypto.randomUUID();
  const hostHeader = req.headers.host;
  const backendHostPort = hostHeader || `${process.env.HOST || "127.0.0.1"}:${process.env.PORT || 8787}`;

  res.json({
    wsUrl: `${wsProtocol}://${backendHostPort}/api/realtime/stream`,
    sessionId
  });
});

const server = http.createServer(app);
const wss = new WebSocketServer({ server, path: "/api/realtime/stream" });

wss.on("connection", (clientWs, req) => {
  const clientIP = req.socket.remoteAddress || "unknown";

  const currentCount = connectionsByIP.get(clientIP) || 0;
  if (currentCount >= MAX_CONNECTIONS_PER_IP) {
    clientWs.close(1013, "Too many connections from this IP");
    return;
  }
  connectionsByIP.set(clientIP, currentCount + 1);

  let pythonProcess = null;
  let lastAudioAt = Date.now();
  let sessionActive = false;
  let closed = false;
  let idleInterval = null;
  // Audio chunk concatenation for model
  let cumulativeAudio = [];
  let isRecording = false;

  const sendToClient = (payload) => {
    if (clientWs.readyState === WebSocket.OPEN) {
      clientWs.send(JSON.stringify(payload));
    }
  };

  const closeAll = (code = 1000, reason = "") => {
    if (closed) return;
    closed = true;
    if (idleInterval) {
      clearInterval(idleInterval);
      idleInterval = null;
    }
    const count = connectionsByIP.get(clientIP) || 1;
    if (count <= 1) {
      connectionsByIP.delete(clientIP);
    } else {
      connectionsByIP.set(clientIP, count - 1);
    }
    try {
      clientWs.close(code, reason);
    } catch (_err) {}
    try {
      if (pythonProcess) {
        pythonProcess.kill();
      }
    } catch (_err) {}
  };

  const spawnPython = () => {
    if (pythonProcess && pythonProcess.exitCode === null) return;
    
    pythonProcess = spawn(PYTHON_VENV_PATH, [TRANSCRIBE_SCRIPT], {
      stdio: ["pipe", "pipe", "pipe"]
    });
    
    const rl = readline.createInterface({ input: pythonProcess.stdout, terminal: false });
    rl.on("line", (line) => {
      try {
        if (!line.trim()) return;
        const msg = JSON.parse(line);
        if (msg.type === "transcript") {
            sendToClient({ type: "final_transcript", text: msg.text });
        } else if (msg.type === "status") {
            console.log("[Python Status]:", msg.state); // Added log
            sendToClient({ type: "status", state: msg.state });
        } else if (msg.type === "error") {
            console.error("[Python Error]:", msg.message); // Added log
            sendToClient({ type: "error", message: msg.message });
        }
      } catch (e) {
          console.error("Failed parsing Python JSON line:", line);
      }
    });

    pythonProcess.stderr.on("data", (data) => {
      console.error("Python Log/Error:", data.toString());
    });
    
    pythonProcess.on("error", (err) => {
      sendToClient({ type: "error", message: "Python process error: " + err.message });
    });

    pythonProcess.stdin.on('error', (err) => {
      if (err.code === 'EPIPE') {
        console.error("Python handler stdin pipe broken (script closed/failed)");
      } else {
        console.error("Python stdin error:", err);
      }
    });

    pythonProcess.on("exit", (code) => {
        if (code !== 0 && code !== null) {
            sendToClient({ type: "error", message: `Python process exited with code ${code}` });
        }
        pythonProcess = null;
    });
  };

  idleInterval = setInterval(() => {
    if (!sessionActive) return;
    const idleMs = Date.now() - lastAudioAt;
    if (idleMs > 60000) {
      sendToClient({ type: "status", state: "idle_timeout" });
      closeAll(1000, "idle_timeout");
    }
  }, 5000);

  // Spawn initially to warm up the model
  spawnPython();

  clientWs.on("message", (data) => {
    let msg;
    try {
      msg = JSON.parse(data.toString());
    } catch (_err) {
      sendToClient({ type: "error", message: "Invalid JSON" });
      return;
    }

    if (msg.type === "start_recording") {
      sessionActive = true;
      isRecording = true;
      cumulativeAudio = []; // clear audio
      spawnPython(); // ensure it's running
      sendToClient({ type: "status", state: "recording" });
      return;
    }

    if (msg.type === "audio_chunk") {
      lastAudioAt = Date.now();
      if (isRecording) {
        cumulativeAudio.push(msg.audio); // Keep collecting base64 or accumulate locally
      }
      return;
    }

    if (msg.type === "stop_and_transcribe") {
      isRecording = false;
      if (cumulativeAudio.length === 0) return; // Prevent duplicate triggers!
      
      sendToClient({ type: "status", state: "processing" });
      if (pythonProcess?.stdin?.writable) {
        const fullBuffer = Buffer.concat(cumulativeAudio.map(a => Buffer.from(a, 'base64')));
        pythonProcess.stdin.write(JSON.stringify({
            type: "transcribe", 
            audio: fullBuffer.toString('base64')
        }) + "\n");
      }
      cumulativeAudio = []; // Clear the buffer to avoid accumulating and duplicating
      return;
    }

    sendToClient({ type: "error", message: "Unknown message type" });
  });

  clientWs.on("close", () => {
    closeAll(1000, "client_closed");
  });

  clientWs.on("error", () => {
    closeAll(1011, "client_error");
  });
});

let hotkeyProcess = null;
const spawnHotkeyListener = () => {
  if (hotkeyProcess) return;
  hotkeyProcess = spawn(PYTHON_VENV_PATH, [HOTKEY_SCRIPT]);
  const rl = readline.createInterface({ input: hotkeyProcess.stdout, terminal: false });
  rl.on("line", (line) => {
    const action = line.trim();
    if (action === "HOTKEY_START") {
      wss.clients.forEach((c) => {
        if (c.readyState === WebSocket.OPEN) c.send(JSON.stringify({ type: "global_hotkey", action: "start" }));
      });
    } else if (action === "HOTKEY_STOP") {
      wss.clients.forEach((c) => {
        if (c.readyState === WebSocket.OPEN) c.send(JSON.stringify({ type: "global_hotkey", action: "stop" }));
      });
    }
  });
  hotkeyProcess.on("exit", () => {
    hotkeyProcess = null;
    setTimeout(spawnHotkeyListener, 5000);
  });
};
spawnHotkeyListener();

server.listen(PORT, HOST, () => {
  console.log(`Backend listening on http://${HOST}:${PORT}`);
});
