import http from "http";
import crypto from "crypto";
import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import { WebSocket, WebSocketServer } from "ws";

dotenv.config();

const PORT = process.env.PORT ? Number(process.env.PORT) : 8787;
const HOST = process.env.HOST || "127.0.0.1";
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const FRONTEND_ORIGIN = process.env.FRONTEND_ORIGIN || "http://localhost:5173";
const MAX_CONNECTIONS_PER_IP = 5;

const connectionsByIP = new Map();

if (!OPENAI_API_KEY) {
  console.warn("Missing OPENAI_API_KEY. Set it in backend/.env");
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

app.post("/api/realtime/session", (req, res) => {
  const protocol = req.headers["x-forwarded-proto"] || req.protocol || "http";
  const host = req.headers["x-forwarded-host"] || req.headers.host;
  const wsProtocol = protocol === "https" ? "wss" : "ws";
  const sessionId = crypto.randomUUID();

  res.json({
    wsUrl: `${wsProtocol}://${host}/api/realtime/stream`,
    sessionId
  });
});

const server = http.createServer(app);
const wss = new WebSocketServer({ server, path: "/api/realtime/stream" });

wss.on("connection", (clientWs, req) => {
  const clientIP = req.socket.remoteAddress || "unknown";

  // Rate limiting by IP
  const currentCount = connectionsByIP.get(clientIP) || 0;
  if (currentCount >= MAX_CONNECTIONS_PER_IP) {
    clientWs.close(1013, "Too many connections from this IP");
    return;
  }
  connectionsByIP.set(clientIP, currentCount + 1);

  let openaiWs = null;
  let lastAudioAt = Date.now();
  let sessionActive = false;
  let closed = false;
  let idleInterval = null;
  let audioQueue = [];

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
    // Decrement connection count for this IP
    const count = connectionsByIP.get(clientIP) || 1;
    if (count <= 1) {
      connectionsByIP.delete(clientIP);
    } else {
      connectionsByIP.set(clientIP, count - 1);
    }
    try {
      clientWs.close(code, reason);
    } catch (_err) {
      // ignore
    }
    try {
      openaiWs?.close();
    } catch (_err) {
      // ignore
    }
  };

  const startOpenAI = ({ language = "es", vad = "none" } = {}) => {
    if (!OPENAI_API_KEY) {
      sendToClient({ type: "error", message: "Missing OPENAI_API_KEY" });
      return;
    }
    if (openaiWs && openaiWs.readyState === WebSocket.OPEN) {
      return;
    }

    const url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17";
    openaiWs = new WebSocket(url, {
      headers: {
        Authorization: `Bearer ${OPENAI_API_KEY}`,
        "OpenAI-Beta": "realtime=v1"
      }
    });

    openaiWs.on("open", () => {
      sessionActive = true;
      sendToClient({ type: "status", state: "openai_connected" });

      openaiWs.send(JSON.stringify({
        type: "session.update",
        session: {
          input_audio_transcription: { model: "whisper-1" },
          turn_detection: { type: "server_vad" },
          modalities: ["text"],
          instructions: "No me respondas con mucho texto, soy el usuario y solo quiero usar el realtime para que me transcribas. Responde conciso si es necesario."
        }
      }));

      // Flush queue
      while (audioQueue.length > 0) {
        openaiWs.send(audioQueue.shift());
      }
    });

    openaiWs.on("message", (data) => {
      let event;
      try {
        event = JSON.parse(data.toString());
      } catch (_err) {
        return;
      }

      if (event.type === "error") {
        sendToClient({ type: "error", message: event.error?.message || "OpenAI error" });
        return;
      }

      // Handle speech detection events
      if (event.type === "input_audio_buffer.speech_started") {
        sendToClient({ type: "speech_started" });
        return;
      }

      if (event.type === "input_audio_buffer.speech_stopped") {
        sendToClient({ type: "speech_stopped" });
        return;
      }

      // Handle ONLY input speech transcript
      if (
        event.type === "conversation.item.input_audio_transcription.completed"
      ) {
        const text = event.transcript || "";
        if (text) {
          sendToClient({ type: "final_transcript", text });
        }
        return;
      }

      // Let user know assistant is speaking (optional)
      if (event.type === "response.text.delta") {
        const text = event.delta || "";
        if (text) sendToClient({ type: "partial_transcript", text });
        return;
      }

      if (event.type === "response.text.done") {
        setImmediate(() => {
            // clear partial after done
            sendToClient({ type: "partial_transcript", text: "" });
        });
      }
    });

    openaiWs.on("close", () => {
      sessionActive = false;
      sendToClient({ type: "status", state: "openai_closed" });
    });

    openaiWs.on("error", (err) => {
      sendToClient({ type: "error", message: err.message || "OpenAI socket error" });
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

  clientWs.on("message", (data) => {
    let msg;
    try {
      msg = JSON.parse(data.toString());
    } catch (_err) {
      sendToClient({ type: "error", message: "Invalid JSON" });
      return;
    }

    if (msg.type === "start") {
      startOpenAI(msg.config);
      sendToClient({ type: "status", state: "listening" });
      return;
    }

    if (msg.type === "audio_chunk") {
      if (typeof msg.audio !== "string") {
        sendToClient({ type: "error", message: "audio_chunk missing base64 audio" });
        return;
      }
      lastAudioAt = Date.now();
      
      const payload = JSON.stringify({
        type: "input_audio_buffer.append",
        audio: msg.audio
      });

      if (!openaiWs || openaiWs.readyState !== WebSocket.OPEN) {
        audioQueue.push(payload);
        return;
      }
      
      openaiWs.send(payload);
      return;
    }

    if (msg.type === "stop") {
      if (openaiWs && openaiWs.readyState === WebSocket.OPEN) {
        openaiWs.send(JSON.stringify({ type: "input_audio_buffer.commit" }));
        openaiWs.send(JSON.stringify({ type: "input_audio_buffer.clear" }));
      }
      closeAll(1000, "client_stop");
      return;
    }

    if (msg.type === "commit") {
      if (openaiWs && openaiWs.readyState === WebSocket.OPEN) {
        openaiWs.send(JSON.stringify({ type: "input_audio_buffer.commit" }));
        sendToClient({ type: "status", state: "processing" });
      }
      return;
    }

    sendToClient({ type: "error", message: "Unknown message type" });
  });

  clientWs.on("close", () => {
    if (idleInterval) {
      clearInterval(idleInterval);
      idleInterval = null;
    }
    // Decrement connection count for this IP
    const count = connectionsByIP.get(clientIP) || 1;
    if (count <= 1) {
      connectionsByIP.delete(clientIP);
    } else {
      connectionsByIP.set(clientIP, count - 1);
    }
    try {
      openaiWs?.close();
    } catch (_err) {
      // ignore
    }
  });

  clientWs.on("error", () => {
    closeAll(1011, "client_error");
  });
});

server.listen(PORT, HOST, () => {
  console.log(`Backend listening on http://${HOST}:${PORT}`);
});
