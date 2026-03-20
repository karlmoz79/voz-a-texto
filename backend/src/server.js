import http from "http";
import crypto from "crypto";
import { spawn } from "child_process";
import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import { WebSocket, WebSocketServer } from "ws";
import path from "path";
import readline from "readline";
import { PCM16_BYTES_PER_SEC, resolveAsrConfig } from "./asr-config.js";
import { createHotkeyOwnerManager } from "./hotkey-owner.js";

dotenv.config();

const PORT = process.env.PORT ? Number(process.env.PORT) : 8787;
const HOST = process.env.HOST || "127.0.0.1";
const FRONTEND_ORIGIN = process.env.FRONTEND_ORIGIN || "http://localhost:5173";
const MAX_CONNECTIONS_PER_IP = 5;
const NATIVE_TYPE_ENABLED = process.env.NATIVE_TYPE_ENABLED === "true";
const NATIVE_TYPE_CMD = process.env.NATIVE_TYPE_CMD || "xdotool";
const GLOBAL_HOTKEY_ENABLED = (process.env.GLOBAL_HOTKEY_ENABLED ?? "true") === "true";

const {
  modelId: ASR_MODEL_ID,
  maxAudioSec: ASR_MAX_AUDIO_SEC,
  usedLegacyModelEnv,
  usedLegacyMaxAudioEnv
} = resolveAsrConfig(process.env);

const MAX_AUDIO_BYTES = Math.floor(ASR_MAX_AUDIO_SEC * PCM16_BYTES_PER_SEC);
const PYTHON_VENV_PATH = path.join(process.cwd(), ".venv", "bin", "python3");
const TRANSCRIBE_SCRIPT = path.join(process.cwd(), "scripts", "transcribe.py");
const HOTKEY_SCRIPT = path.join(process.cwd(), "scripts", "hotkey.py");

const connectionsByIP = new Map();
const clientSessions = new Map();
const hotkeyOwnerManager = createHotkeyOwnerManager();

if (usedLegacyModelEnv) {
  console.warn("[ASR] Using deprecated PARAKEET_MODEL_PATH. Prefer ASR_MODEL_ID.");
}

if (usedLegacyMaxAudioEnv) {
  console.warn("[ASR] Using deprecated PARAKEET_MAX_AUDIO_SEC. Prefer ASR_MAX_AUDIO_SEC.");
}

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
  const backendHostPort = hostHeader || `${HOST}:${PORT}`;

  res.json({
    wsUrl: `${wsProtocol}://${backendHostPort}/api/realtime/stream`,
    sessionId,
    maxAudioSec: ASR_MAX_AUDIO_SEC
  });
});

const server = http.createServer(app);
const wss = new WebSocketServer({ server, path: "/api/realtime/stream" });

let hotkeyProcess = null;
let hotkeyListenerDisabled = false;

const sendJson = (ws, payload) => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
  }
};

const isHotkeyAvailable = () =>
  GLOBAL_HOTKEY_ENABLED &&
  process.platform === "linux" &&
  !hotkeyListenerDisabled;

const notifyHotkeyOwnership = () => {
  clientSessions.forEach((session, ws) => {
    const isOwner =
      isHotkeyAvailable() &&
      Boolean(session.sessionId) &&
      hotkeyOwnerManager.isOwner(session.sessionId);

    sendJson(ws, { type: "hotkey_owner", isOwner });
  });
};

const dispatchGlobalHotkey = (action) => {
  if (!isHotkeyAvailable()) return;

  const ownerSessionId = hotkeyOwnerManager.getOwnerSessionId();
  if (!ownerSessionId) return;

  clientSessions.forEach((session, ws) => {
    if (session.sessionId === ownerSessionId) {
      sendJson(ws, { type: "global_hotkey", action });
    }
  });
};

const disableHotkeyListener = (reason) => {
  if (hotkeyListenerDisabled) return;

  hotkeyListenerDisabled = true;
  console.warn(`[Hotkey] Global listener disabled: ${reason}`);

  if (hotkeyProcess) {
    try {
      hotkeyProcess.kill();
    } catch (_err) {}
    hotkeyProcess = null;
  }

  notifyHotkeyOwnership();
};

const spawnHotkeyListener = () => {
  if (!GLOBAL_HOTKEY_ENABLED) {
    console.log("[Hotkey] Global listener disabled by GLOBAL_HOTKEY_ENABLED=false");
    return;
  }
  if (process.platform !== "linux") {
    console.log("[Hotkey] Global listener only runs on Linux");
    return;
  }
  if (hotkeyListenerDisabled || hotkeyProcess) {
    return;
  }

  hotkeyProcess = spawn(PYTHON_VENV_PATH, [HOTKEY_SCRIPT], {
    stdio: ["ignore", "pipe", "pipe"]
  });

  let ready = false;
  const hotkeyOutput = readline.createInterface({
    input: hotkeyProcess.stdout,
    terminal: false
  });

  hotkeyOutput.on("line", (line) => {
    const action = line.trim();

    if (action === "READY") {
      ready = true;
      notifyHotkeyOwnership();
      return;
    }
    if (action === "HOTKEY_START") {
      dispatchGlobalHotkey("start");
      return;
    }
    if (action === "HOTKEY_STOP") {
      dispatchGlobalHotkey("stop");
    }
  });

  hotkeyProcess.stderr.on("data", (data) => {
    console.error("Hotkey listener log:", data.toString());
  });

  hotkeyProcess.on("error", (err) => {
    disableHotkeyListener(err.message || "Unknown hotkey listener error");
  });

  hotkeyProcess.on("exit", (code, signal) => {
    hotkeyProcess = null;

    if (hotkeyListenerDisabled) return;
    if (code === 0 && signal === null) return;

    const hint = ready
      ? "listener exited unexpectedly"
      : "listener failed to start";
    const reason = code == null ? hint : `${hint} (code ${code})`;

    disableHotkeyListener(reason);
  });
};

wss.on("connection", (clientWs, req) => {
  const clientIP = req.socket.remoteAddress || "unknown";
  const currentCount = connectionsByIP.get(clientIP) || 0;

  if (currentCount >= MAX_CONNECTIONS_PER_IP) {
    clientWs.close(1013, "Too many connections from this IP");
    return;
  }

  connectionsByIP.set(clientIP, currentCount + 1);

  const session = {
    sessionId: null,
    wantsHotkeyControl: true,
    pythonProcess: null,
    lastAudioAt: Date.now(),
    isRecording: false,
    closed: false,
    idleInterval: null,
    cumulativeAudio: [],
    cumulativeAudioBytes: 0,
    recordingTooLong: false
  };

  clientSessions.set(clientWs, session);

  const sendToClient = (payload) => {
    sendJson(clientWs, payload);
  };

  const sendStatus = (state) => {
    sendToClient({ type: "status", state });
  };

  const clearAudioBuffer = () => {
    session.cumulativeAudio = [];
    session.cumulativeAudioBytes = 0;
    session.recordingTooLong = false;
  };

  const releaseHotkeyOwnership = () => {
    if (!session.sessionId) return;
    hotkeyOwnerManager.unregister(session.sessionId);
    session.sessionId = null;
    notifyHotkeyOwnership();
  };

  const closeAll = (code = 1000, reason = "") => {
    if (session.closed) return;
    session.closed = true;

    if (session.idleInterval) {
      clearInterval(session.idleInterval);
      session.idleInterval = null;
    }

    const count = connectionsByIP.get(clientIP) || 1;
    if (count <= 1) {
      connectionsByIP.delete(clientIP);
    } else {
      connectionsByIP.set(clientIP, count - 1);
    }

    clientSessions.delete(clientWs);
    releaseHotkeyOwnership();
    clearAudioBuffer();
    session.isRecording = false;

    try {
      clientWs.close(code, reason);
    } catch (_err) {}

    try {
      if (session.pythonProcess) {
        session.pythonProcess.kill();
      }
    } catch (_err) {}
  };

  const spawnPython = () => {
    if (session.pythonProcess && session.pythonProcess.exitCode === null) {
      return;
    }

    session.pythonProcess = spawn(PYTHON_VENV_PATH, [TRANSCRIBE_SCRIPT], {
      stdio: ["pipe", "pipe", "pipe"],
      env: {
        ...process.env,
        ASR_MODEL_ID,
        ASR_MAX_AUDIO_SEC: String(ASR_MAX_AUDIO_SEC)
      }
    });

    const pythonOutput = readline.createInterface({
      input: session.pythonProcess.stdout,
      terminal: false
    });

    pythonOutput.on("line", (line) => {
      if (!line.trim()) return;

      try {
        const msg = JSON.parse(line);

        if (msg.type === "transcript") {
          sendToClient({ type: "final_transcript", text: msg.text || "" });
          sendStatus("ready");
          return;
        }

        if (msg.type === "status" && typeof msg.state === "string") {
          sendStatus(msg.state);
          return;
        }

        if (msg.type === "error") {
          sendToClient({ type: "error", message: msg.message || "Unknown Python error" });
          sendStatus("ready");
        }
      } catch (_err) {
        console.error("Failed parsing Python JSON line:", line);
      }
    });

    session.pythonProcess.stderr.on("data", (data) => {
      console.error("Python log/error:", data.toString());
    });

    session.pythonProcess.on("error", (err) => {
      sendToClient({
        type: "error",
        message: `Python process error: ${err.message}`
      });
    });

    session.pythonProcess.stdin.on("error", (err) => {
      if (err.code === "EPIPE") {
        console.error("Python stdin pipe broken");
      } else {
        console.error("Python stdin error:", err);
      }
    });

    session.pythonProcess.on("exit", (code) => {
      if (!session.closed && code !== 0 && code !== null) {
        sendToClient({
          type: "error",
          message: `Python process exited with code ${code}`
        });
      }

      session.pythonProcess = null;
    });
  };

  const registerClient = (msg) => {
    if (typeof msg.sessionId !== "string" || msg.sessionId.trim().length === 0) {
      sendToClient({ type: "error", message: "Missing sessionId" });
      return;
    }

    if (session.sessionId && session.sessionId !== msg.sessionId) {
      hotkeyOwnerManager.unregister(session.sessionId);
    }

    session.sessionId = msg.sessionId.trim();
    session.wantsHotkeyControl = msg.wantsHotkeyControl !== false;
    hotkeyOwnerManager.setEligible(session.sessionId, session.wantsHotkeyControl);
    notifyHotkeyOwnership();
  };

  session.idleInterval = setInterval(() => {
    if (!session.isRecording) return;

    const idleMs = Date.now() - session.lastAudioAt;
    if (idleMs > 60000) {
      sendStatus("idle_timeout");
      closeAll(1000, "idle_timeout");
    }
  }, 5000);

  spawnPython();
  notifyHotkeyOwnership();

  clientWs.on("message", (data) => {
    let msg;

    try {
      msg = JSON.parse(data.toString());
    } catch (_err) {
      sendToClient({ type: "error", message: "Invalid JSON" });
      return;
    }

    if (msg.type === "register_client") {
      registerClient(msg);
      return;
    }

    if (msg.type === "start_recording") {
      session.isRecording = true;
      session.lastAudioAt = Date.now();
      clearAudioBuffer();
      spawnPython();
      sendStatus("recording");
      return;
    }

    if (msg.type === "audio_chunk") {
      if (!session.isRecording || typeof msg.audio !== "string") {
        return;
      }

      session.lastAudioAt = Date.now();

      if (session.recordingTooLong) {
        return;
      }

      const chunkBuffer = Buffer.from(msg.audio, "base64");
      if (chunkBuffer.length === 0) {
        return;
      }

      const nextTotalBytes = session.cumulativeAudioBytes + chunkBuffer.length;
      if (nextTotalBytes > MAX_AUDIO_BYTES) {
        session.recordingTooLong = true;
        return;
      }

      session.cumulativeAudio.push(chunkBuffer);
      session.cumulativeAudioBytes = nextTotalBytes;
      return;
    }

    if (msg.type === "stop_and_transcribe") {
      session.isRecording = false;

      if (session.recordingTooLong) {
        clearAudioBuffer();
        sendToClient({
          type: "error",
          message: `El audio supero el maximo de ${ASR_MAX_AUDIO_SEC} segundos.`
        });
        sendStatus("ready");
        return;
      }

      if (session.cumulativeAudioBytes === 0) {
        clearAudioBuffer();
        sendStatus("ready");
        return;
      }

      if (!session.pythonProcess?.stdin?.writable) {
        clearAudioBuffer();
        sendToClient({
          type: "error",
          message: "El proceso de transcripcion no esta listo."
        });
        sendStatus("ready");
        return;
      }

      sendStatus("processing");

      const fullBuffer = Buffer.concat(session.cumulativeAudio);
      session.pythonProcess.stdin.write(
        `${JSON.stringify({
          type: "transcribe",
          audio: fullBuffer.toString("base64")
        })}\n`
      );

      clearAudioBuffer();
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

spawnHotkeyListener();

server.listen(PORT, HOST, () => {
  console.log(`Backend listening on http://${HOST}:${PORT}`);
  console.log(`[ASR] Default model: ${ASR_MODEL_ID}`);
});
