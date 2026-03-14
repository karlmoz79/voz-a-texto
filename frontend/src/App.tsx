import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const TARGET_SAMPLE_RATE = 24000;
const CHUNK_SAMPLES = 480; // 20ms @ 24kHz
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
  const [isPaused, setIsPaused] = useState(false);
  const isPausedRef = useRef(false);
  const [language, setLanguage] = useState("es");
  const [partials, setPartials] = useState("");
  const [finals, setFinals] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const pendingSamplesRef = useRef<number[]>([]);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const mergedTranscript = useMemo(() => finals.join(" "), [finals]);

  const pauseSession = useCallback(() => {
    isPausedRef.current = true;
    setIsPaused(true);
    setStatus("Pausado - clickea procesar");
  }, []);

  const processAndResume = useCallback(() => {
    const ws = wsRef.current;
    
    if (ws && ws.readyState === WebSocket.OPEN) {
      const pending = pendingSamplesRef.current;
      
      while (pending.length >= CHUNK_SAMPLES) {
        const chunk = new Int16Array(CHUNK_SAMPLES);
        for (let i = 0; i < CHUNK_SAMPLES; i += 1) {
          chunk[i] = pending.shift() as number;
        }
        ws.send(JSON.stringify({ type: "audio_chunk", audio: pcm16ToBase64(chunk) }));
      }
      
      if (pending.length > 0) {
        const chunk = new Int16Array(pending.length);
        for (let i = 0; i < pending.length; i += 1) {
          chunk[i] = pending[i] as number;
        }
        pending.length = 0;
        ws.send(JSON.stringify({ type: "audio_chunk", audio: pcm16ToBase64(chunk) }));
      }
      
      ws.send(JSON.stringify({ type: "commit" }));
    }
    
    isPausedRef.current = false;
    setIsPaused(false);
    setStatus("Escuchando...");
  }, []);

  const stopSession = useCallback(() => {
    isPausedRef.current = false;
    setIsPaused(false);

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
    setStatus("Stopped");
  }, []);

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
        } catch (err) {
          setError("Permiso de micrófono denegado o no disponible");
          setStatus("Error");
        }
      };

      ws.onmessage = (event) => {
        let msg: { type?: string; text?: string; message?: string; state?: string } = {};
        try {
          msg = JSON.parse(event.data);
        } catch (_err) {
          return;
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
            setPartials("");
            setStatus("Escuchando...");
          }
        }

        if (msg.type === "status") {
          if (msg.state === "listening" || msg.state === "openai_connected") setStatus("Escuchando...");
          if (msg.state === "openai_closed") setStatus("Cerrado");
          if (msg.state === "idle_timeout") setStatus("Tiempo de inactividad agotado");
        }

        if (msg.type === "error") {
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

      if (!isPausedRef.current) {
        while (pending.length >= CHUNK_SAMPLES) {
          const chunk = new Int16Array(CHUNK_SAMPLES);
          for (let i = 0; i < CHUNK_SAMPLES; i += 1) {
            chunk[i] = pending.shift() as number;
          }
          sendAudioChunk(chunk);
        }
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
          <p>Transcripción en tiempo real con OpenAI Realtime + Whisper</p>
        </div>
        <div className={`status ${statusClass}`}>
          <span>Estado</span>
          <strong>{status}</strong>
        </div>
      </header>

      <section className="controls">
        <label>
          Idioma
          <select value={language} onChange={(e) => setLanguage(e.target.value)}>
            <option value="es">Español</option>
            <option value="en">English</option>
            <option value="pt">Português</option>
          </select>
        </label>

        <div className="buttons">
          <button onClick={startSession} disabled={status === "Escuchando..." || isPaused}>
            Iniciar
          </button>
          {wsRef.current && !isPaused && (
            <button onClick={pauseSession}>Pausar</button>
          )}
          {isPaused && (
            <button onClick={processAndResume}>Procesar</button>
          )}
          <button onClick={stopSession} disabled={!wsRef.current}>
            Detener
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
