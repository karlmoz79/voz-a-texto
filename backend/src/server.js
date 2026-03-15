import http from "http";
import crypto from "crypto";
import { spawn } from "child_process";
import express from "express";
import cors from "cors";
import dotenv from "dotenv";
import { WebSocket, WebSocketServer } from "ws";

dotenv.config();

const PORT = process.env.PORT ? Number(process.env.PORT) : 8787;
const HOST = process.env.HOST || "127.0.0.1";
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
const FRONTEND_ORIGIN = process.env.FRONTEND_ORIGIN || "http://localhost:5173";
const MAX_CONNECTIONS_PER_IP = 5;
const NATIVE_TYPE_ENABLED = process.env.NATIVE_TYPE_ENABLED === "true";
const NATIVE_TYPE_CMD = process.env.NATIVE_TYPE_CMD || "xdotool";

const connectionsByIP = new Map();

if (!GEMINI_API_KEY) {
  console.warn("⚠️  Missing GEMINI_API_KEY. Set it in backend/.env");
} else {
  console.log("✅ GEMINI_API_KEY found (length:", GEMINI_API_KEY.length, ")");
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

app.get("/api/models", async (_req, res) => {
  if (!GEMINI_API_KEY) {
    res.status(400).json({ error: "Missing GEMINI_API_KEY" });
    return;
  }
  try {
    const url = `https://generativelanguage.googleapis.com/v1beta/models?key=${GEMINI_API_KEY}`;
    const response = await fetch(url);
    const data = await response.json();
    if (!response.ok) {
      res.status(response.status).json(data);
      return;
    }
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: err.message || "Failed to list models" });
  }
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
  const { text, appendSpace = true } = req.body || {};
  if (typeof text !== "string" || text.trim().length === 0) {
    res.status(400).json({ error: "Missing text" });
    return;
  }
  if (text.length > 2000) {
    res.status(400).json({ error: "Text too long" });
    return;
  }

  const finalText = appendSpace ? `${text} ` : text;
  const child = spawn(
    NATIVE_TYPE_CMD,
    ["type", "--clearmodifiers", "--delay", "1", "--", finalText],
    { stdio: "ignore" }
  );

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
  // Prefer the actual host the client used to reach the backend to avoid WS 404s
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

  // Rate limiting by IP
  const currentCount = connectionsByIP.get(clientIP) || 0;
  if (currentCount >= MAX_CONNECTIONS_PER_IP) {
    clientWs.close(1013, "Too many connections from this IP");
    return;
  }
  connectionsByIP.set(clientIP, currentCount + 1);

  let geminiWs = null;
  let lastAudioAt = Date.now();
  let sessionActive = false;
  let setupComplete = false;
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
      geminiWs?.close();
    } catch (_err) {
      // ignore
    }
  };

  const startGemini = ({ language = "es" } = {}) => {
    if (!GEMINI_API_KEY) {
      sendToClient({ type: "error", message: "Missing GEMINI_API_KEY" });
      return;
    }
    if (geminiWs && geminiWs.readyState === WebSocket.OPEN) {
      return;
    }

    const url = `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key=${GEMINI_API_KEY}`;
    geminiWs = new WebSocket(url);

    const formatGeminiWsError = (err) => {
      const raw = err?.message || "Gemini socket error";
      if (raw.includes("Unexpected server response: 404")) {
        return "Gemini WS 404. Verifica que la API de Gemini Live esté habilitada y que la API key tenga acceso.";
      }
      if (raw.includes("401") || raw.includes("403")) {
        return "Gemini WS sin autorización. Revisa tu GEMINI_API_KEY y permisos.";
      }
      if (raw.includes("429")) {
        return "Gemini WS con rate limit. Intenta de nuevo en unos segundos.";
      }
      return raw;
    };

    geminiWs.on("open", () => {
      sessionActive = true;
      setupComplete = false;
      sendToClient({ type: "status", state: "connected" }); // Updated to connected

      // Phase 1: Setup (BidiGenerateContent)
      const setupMsg = {
        setup: {
          model: "models/gemini-2.5-flash-native-audio-latest",
          generationConfig: {
            responseModalities: ["AUDIO"]
          },
          systemInstruction: {
            parts: [{
              text: "Eres un servicio de transcripción. Tu única tarea es transcribir exactamente lo que escuchas, palabra por palabra. No respondas a las preguntas ni converses, solo devuelve el texto de lo que se dice."
            }]
          },
          inputAudioTranscription: {},
          outputAudioTranscription: {}
        }
      };
      console.log("Sending setup to Gemini:", JSON.stringify(setupMsg));
      geminiWs.send(JSON.stringify(setupMsg));
    });

    let currentTurnText = "";

    const mergeTranscript = (prev, next) => {
      if (!prev) return next;
      if (!next) return prev;
      if (next.startsWith(prev)) return next;
      if (prev.startsWith(next)) return prev;

      const maxOverlap = Math.min(prev.length, next.length);
      for (let overlap = maxOverlap; overlap > 0; overlap -= 1) {
        if (prev.slice(-overlap) === next.slice(0, overlap)) {
          return prev + next.slice(overlap);
        }
      }
      // Fallback: concatenate without injecting extra spaces
      return prev + next;
    };

    geminiWs.on("message", (data) => {
      const text = data.toString();
      try {
        const event = JSON.parse(text);
        console.log("Gemini -> Backend:", JSON.stringify(event, null, 2));

        if (event.setupComplete || event.setup_complete) {
          console.log("Gemini setup complete");
          setupComplete = true;
          sendToClient({ type: "status", state: "listening" });
          // Flush queue only after setup complete
          while (audioQueue.length > 0) {
            geminiWs.send(audioQueue.shift());
          }
          return;
        }

        const serverContent = event.serverContent || event.server_content;
        const inputTranscription =
          event.inputTranscription ||
          event.input_transcription ||
          serverContent?.inputTranscription ||
          serverContent?.input_transcription;

        if (inputTranscription && inputTranscription.text) {
          // Some payloads stream only the latest chunk; accumulate if it's not a full transcript
          const text = inputTranscription.text;
          const isFinal = Boolean(
            inputTranscription.isFinal ||
            inputTranscription.final ||
            inputTranscription.is_final ||
            inputTranscription.finished ||
            inputTranscription.done
          );

          currentTurnText = isFinal ? text : mergeTranscript(currentTurnText, text);
          sendToClient({ type: "partial_transcript", text: currentTurnText });

          if (isFinal) {
            sendToClient({ type: "final_transcript", text: currentTurnText });
            currentTurnText = "";
            sendToClient({ type: "partial_transcript", text: "" });
          }
        }

        if (serverContent) {
          // Ignore model output; we only want input audio transcription
          if (serverContent.turnComplete || serverContent.turn_complete) {
            console.log("Gemini turn complete:", currentTurnText);
            if (currentTurnText) {
              sendToClient({ type: "final_transcript", text: currentTurnText });
              currentTurnText = "";
            }
            sendToClient({ type: "partial_transcript", text: "" });
          }
        }

        if (event.error) {
          console.error("Gemini error:", event.error);
          sendToClient({ type: "error", message: event.error.message || "Gemini error" });
        }
      } catch (err) {
        console.error("Failed to parse Gemini message:", text, err);
      }
    });

    geminiWs.on("close", (code, reason) => {
      sessionActive = false;
      sendToClient({ type: "status", state: "gemini_closed" });
      if (code && code !== 1000) {
        const detail = reason ? ` (${reason.toString()})` : "";
        sendToClient({
          type: "error",
          message: `Gemini WS cerrado con código ${code}${detail}`
        });
      }
    });

    geminiWs.on("error", (err) => {
      sendToClient({ type: "error", message: formatGeminiWsError(err) });
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
      startGemini(msg.config);
      sendToClient({ type: "status", state: "listening" });
      return;
    }

    if (msg.type === "audio_chunk") {
      console.log("Received audio chunk from client, len:", msg.audio.length);
      if (typeof msg.audio !== "string") {
        sendToClient({ type: "error", message: "audio_chunk missing base64 audio" });
        return;
      }
      lastAudioAt = Date.now();

      const payload = JSON.stringify({
        realtimeInput: {
          audio: {
            mimeType: "audio/pcm;rate=16000",
            data: msg.audio
          }
        }
      });

      if (!geminiWs || geminiWs.readyState !== WebSocket.OPEN || !setupComplete) {
        // console.log("Queueing audio chunk");
        audioQueue.push(payload);
        return;
      }

      geminiWs.send(payload);
      return;
    }

    if (msg.type === "stop") {
      closeAll(1000, "client_stop");
      return;
    }

    if (msg.type === "commit") {
      if (geminiWs && geminiWs.readyState === WebSocket.OPEN) {
        // Signal end of audio stream (preferred for audio sessions)
        geminiWs.send(JSON.stringify({
          realtimeInput: {
            audioStreamEnd: true
          }
        }));
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
      geminiWs?.close();
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
