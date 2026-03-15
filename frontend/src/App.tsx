import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const TARGET_SAMPLE_RATE = 16000;
const CHUNK_SAMPLES = 320; // 20ms @ 16kHz
const MAX_RECONNECT_ATTEMPTS = 3;
const RECONNECT_BASE_DELAY_MS = 1000;

function resampleFloat32(input: Float32Array, inRate: number, outRate: number) {
  if (inRate === outRate) return input;
  const ratio = inRate / outRate;
  const outLength = Math.round(input.length / ratio);
  const output = new Float32Array(outLength);
  for (let i = 0; i < outLength; i += 1) {
    const srcIndex = i * ratio;
    const index0 = Math.floor(srcIndex);
    const index1 = Math.min(index0 + 1, input.length - 1);
    const frac = srcIndex - index0;
    output[i] = input[index0] * (1 - frac) + input[index1] * frac;
  }
  return output;
}

function floatToPCM16(input: Float32Array) {
  const output = new Int16Array(input.length);
  for (let i = 0; i < input.length; i += 1) {
    const s = Math.max(-1, Math.min(1, input[i]));
    output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return output;
}

function pcm16ToBase64(pcm: Int16Array) {
  const bytes = new Uint8Array(pcm.buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

export default function App() {
  const [status, setStatus] = useState("Idle");
  const [language, setLanguage] = useState("es");
  const [partials, setPartials] = useState("");
  const [finals, setFinals] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [nativeTyping, setNativeTyping] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const pendingSamplesRef = useRef<number[]>([]);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const mergedTranscript = useMemo(() => finals.join(" "), [finals]);

  const sendNativeText = useCallback(async (text: string) => {
    try {
      const res = await fetch("/api/native/type", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        setError(data?.error || "No se pudo enviar texto a la ventana activa");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al enviar texto a la ventana activa");
    }
  }, []);

  const stopSession = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    reconnectAttemptsRef.current = 0;

    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "stop" }));
      ws.close();
    }
    wsRef.current = null;

    workletNodeRef.current?.disconnect();
    workletNodeRef.current = null;

    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;

    audioContextRef.current?.close();
    audioContextRef.current = null;

    pendingSamplesRef.current = [];
    setStatus("Detenido");
    setRecording(false);
  }, []);

  const finishAndTranscribe = useCallback(() => {
    // Apagar micrófono visualmente
    workletNodeRef.current?.disconnect();
    workletNodeRef.current = null;
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
    audioContextRef.current?.close();
    audioContextRef.current = null;
    setRecording(false);

    // Enviar pendientes y comando commit al backend
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      const pending = pendingSamplesRef.current;
      if (pending.length > 0) {
        const chunk = new Int16Array(pending.length);
        for (let i = 0; i < pending.length; i += 1) {
          chunk[i] = pending[i] as number;
        }
        pending.length = 0;
        ws.send(JSON.stringify({ type: "audio_chunk", audio: pcm16ToBase64(chunk) }));
      }
      ws.send(JSON.stringify({ type: "commit" }));
      setStatus("Procesando transcripción...");
    } else {
      stopSession();
    }
  }, [stopSession]);

  useEffect(() => {
    return () => {
      stopSession();
    };
  }, [stopSession]);

  const startSession = async () => {
    if (wsRef.current) return;
    setError(null);
    setStatus("Creando sesión...");
    setPartials("");
    setFinals([]);

    const res = await fetch("/api/realtime/session", { method: "POST" });
    if (!res.ok) {
      setError("No se pudo crear la sesión");
      setStatus("Error");
      return;
    }
    const { wsUrl } = await res.json();
    setStatus("Conectando al servidor...");

    const connectWebSocket = (attempt = 0) => {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = async () => {
        reconnectAttemptsRef.current = 0;
        setStatus("Conectado, iniciando audio...");
        ws.send(
          JSON.stringify({
            type: "start",
            config: { language, vad: "none" }
          })
        );
        try {
          setStatus("Solicitando permiso de micrófono...");
          await startAudio();
          setStatus("Escuchando...");
          setRecording(true);
        } catch (err) {
          setError("Permiso de micrófono denegado o no disponible");
          setStatus("Error");
          setRecording(false);
        }
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        console.log("WebSocket event:", msg);

        if (msg.type === "status") {
          if (msg.state === "listening" || msg.state === "connected") {
            setStatus("Escuchando...");
            setRecording(true);
          }
          if (msg.state === "processing") setStatus("Procesando transcripción...");
          if (msg.state === "openai_closed" || msg.state === "gemini_closed") {
            setStatus("Sesión cerrada");
            setRecording(false);
          }
        }

        if (msg.type === "speech_started") {
          setStatus("Hablando...");
        }

        if (msg.type === "partial_transcript") {
          setPartials(msg.text || "");
          setStatus("Transcribiendo...");
        }

        if (msg.type === "final_transcript") {
          if (msg.text) {
            setFinals((prev) => [...prev, msg.text as string]);
            if (nativeTyping) {
              void sendNativeText(msg.text as string);
            }
          }
          setPartials("");
          // Si el micrófono está apagado, significa que se llamó a finishAndTranscribe
          if (!workletNodeRef.current) {
            stopSession();
          } else {
            setStatus("Escuchando...");
          }
        }

        if (msg.type === "error") {
          if (msg.message && msg.message.includes("buffer too small")) {
            if (!workletNodeRef.current) {
              stopSession();
            }
            return;
          }
          setError(msg.message || "Error");
          setStatus("Error");
        }
      };

      ws.onerror = () => {
        setError("Error de conexión");
        setStatus("Error");
      };

      ws.onclose = (event) => {
        wsRef.current = null;

        if (event.code !== 1000 && attempt < MAX_RECONNECT_ATTEMPTS) {
          const delay = RECONNECT_BASE_DELAY_MS * Math.pow(2, attempt);
          setStatus(`Reconectando en ${delay / 1000}s...`);
          reconnectTimeoutRef.current = setTimeout(() => {
            connectWebSocket(attempt + 1);
          }, delay);
        } else {
          // If already in 'Procesando...', we let it finish or error, otherwise:
          setStatus("Detenido");
        }
      };
    };

    connectWebSocket();
  };

  const startAudio = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaStreamRef.current = stream;

    const audioContext = new AudioContext();
    audioContextRef.current = audioContext;

    await audioContext.audioWorklet.addModule(
      new URL("./audio-worklet.ts", import.meta.url)
    );

    const source = audioContext.createMediaStreamSource(stream);
    const workletNode = new AudioWorkletNode(audioContext, "pcm-worklet");
    workletNodeRef.current = workletNode;

    workletNode.port.onmessage = (event) => {
      const input = event.data as Float32Array;
      const resampled = resampleFloat32(input, audioContext.sampleRate, TARGET_SAMPLE_RATE);
      const pcm16 = floatToPCM16(resampled);

      const pending = pendingSamplesRef.current;
      for (let i = 0; i < pcm16.length; i += 1) {
        pending.push(pcm16[i]);
      }

      while (pending.length >= CHUNK_SAMPLES) {
        const chunk = new Int16Array(CHUNK_SAMPLES);
        for (let i = 0; i < CHUNK_SAMPLES; i += 1) {
          chunk[i] = pending.shift() as number;
        }
        sendAudioChunk(chunk);
      }
    };

    source.connect(workletNode);
    const mute = audioContext.createGain();
    mute.gain.value = 0;
    workletNode.connect(mute).connect(audioContext.destination);
  };

  const sendAudioChunk = (chunk: Int16Array) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(
      JSON.stringify({
        type: "audio_chunk",
        audio: pcm16ToBase64(chunk)
      })
    );
  };

  const statusClass = status === "Error" ? "status-error"
    : status.includes("Escuchando") || status.includes("Hablando") || status.includes("Transcribiendo") || status.includes("Procesando")
      ? "status-listening"
      : "";

  const exportTranscript = () => {
    const blob = new Blob([mergedTranscript], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "transcript.txt";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Voz a Texto</h1>
          <p>Transcripción en tiempo real con Gemini Multimodal Live</p>
        </div>
        <div className={`status ${statusClass}`}>
          <span>Estado</span>
          <strong>{status}</strong>
        </div>
      </header>

      <section className="controls">
        <label>
          Idioma
          <select value={language} onChange={(e) => setLanguage(e.target.value)} disabled={!!wsRef.current}>
            <option value="es">Español</option>
            <option value="en">English</option>
            <option value="pt">Português</option>
          </select>
        </label>

        <label>
          Dictado nativo
          <input
            type="checkbox"
            checked={nativeTyping}
            onChange={(e) => setNativeTyping(e.target.checked)}
          />
        </label>

        <div className="buttons">
          <button onClick={startSession} disabled={status === "Escuchando..." || status === "Procesando transcripción..." || !!wsRef.current}>
            Iniciar
          </button>
          
          <button onClick={stopSession} disabled={!wsRef.current}>
            Detener
          </button>

          <button onClick={finishAndTranscribe} disabled={!wsRef.current || status === "Procesando transcripción..."}>
            Procesar
          </button>
          
          <button onClick={exportTranscript} disabled={!mergedTranscript}>
            Exportar texto
          </button>
        </div>
      </section>

      {error && <div className="error">{error}</div>}

      <section className="transcript">
        <h2>Transcripción</h2>
        <div className="final">{mergedTranscript}</div>
        {partials && <div className="partial">{partials}</div>}
      </section>
    </div>
  );
}
