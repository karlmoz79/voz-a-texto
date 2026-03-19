import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";

const TARGET_SAMPLE_RATE = 16000;
const CHUNK_SAMPLES = 2560; // 160ms @ 16kHz
const NATIVE_FLUSH_INTERVAL_MS = 16;
const MAX_PENDING_SAMPLES = Math.floor(TARGET_SAMPLE_RATE * 0.5);
const WAVE_BARS = Array.from({ length: 13 }, (_, i) => i);

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

function appendOnlyDelta(current: string, desired: string) {
  if (!desired) {
    return { append: "", nextTyped: current };
  }
  if (!current) {
    return { append: desired, nextTyped: desired };
  }
  if (desired.startsWith(current)) {
    return { append: desired.slice(current.length), nextTyped: desired };
  }

  const maxOverlap = Math.min(current.length, desired.length);
  for (let overlap = maxOverlap; overlap > 0; overlap -= 1) {
    if (current.slice(-overlap) === desired.slice(0, overlap)) {
      const append = desired.slice(overlap);
      return { append, nextTyped: current + append };
    }
  }

  const needsSpace = !current.endsWith(" ") && !desired.startsWith(" ");
  const append = needsSpace ? ` ${desired}` : desired;
  return { append, nextTyped: current + append };
}

export default function App() {
  const [status, setStatus] = useState("Inactivo");
  const [language, setLanguage] = useState("es");
  const [partials, setPartials] = useState("");
  const [finals, setFinals] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [nativeTyping, setNativeTyping] = useState(true);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const pendingSamplesRef = useRef<number[]>([]);
  
  const connectedRef = useRef(false);

  // Native typing state
  const nativeTypingRef = useRef(nativeTyping);
  const nativeDesiredRef = useRef("");
  const nativeSessionTextRef = useRef("");
  const nativeInFlightRef = useRef(false);
  const nativeCommitPendingRef = useRef(false);
  const nativeAfterCommitRef = useRef<string | null>(null);
  const nativeStopPendingRef = useRef(false);
  const nativeFlushTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const mergedTranscript = useMemo(() => finals.join(" "), [finals]);
  const showWave = recording && status !== "Error" && !status.includes("Procesando");

  const sendNativeText = useCallback(async (
    text: string,
    backspaces = 0,
    appendSpace = false,
    delayMs = 1
  ) => {
    try {
      if (!text && backspaces <= 0) return true;
      const res = await fetch("/api/native/type", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, backspaces, appendSpace, delayMs })
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        setError(data?.error || "No se pudo enviar texto a la ventana activa");
        return false;
      }
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al enviar texto a la ventana activa");
      return false;
    }
  }, []);

  const resetNativeBuffer = useCallback(() => {
    nativeDesiredRef.current = "";
    nativeSessionTextRef.current = "";
    nativeCommitPendingRef.current = false;
    nativeInFlightRef.current = false;
    nativeAfterCommitRef.current = null;
    nativeStopPendingRef.current = false;
    if (nativeFlushTimeoutRef.current) {
      clearTimeout(nativeFlushTimeoutRef.current);
      nativeFlushTimeoutRef.current = null;
    }
  }, []);

  const flushNative = async () => {
    if (!nativeTypingRef.current || nativeInFlightRef.current) return;
    const desired = nativeDesiredRef.current;
    const current = nativeSessionTextRef.current;
    const commit = nativeCommitPendingRef.current;

    if (desired === current && !commit) return;
    const { append, nextTyped } = appendOnlyDelta(current, desired);
    if (!append) {
      if (commit) {
        nativeCommitPendingRef.current = false;
        if (nativeAfterCommitRef.current) {
          nativeDesiredRef.current = nativeAfterCommitRef.current;
          nativeAfterCommitRef.current = null;
          scheduleNativeFlush();
        }
      }
      return;
    }

    const desiredAtSend = desired;
    nativeInFlightRef.current = true;
    try {
      const ok = await sendNativeText(append, 0, false, 1);
      if (ok) {
        nativeSessionTextRef.current = nextTyped;
        if (commit) {
          nativeCommitPendingRef.current = false;
          if (nativeAfterCommitRef.current) {
            nativeDesiredRef.current = nativeAfterCommitRef.current;
            nativeAfterCommitRef.current = null;
            scheduleNativeFlush();
          }
        }
      } else {
        scheduleNativeFlush();
      }
    } finally {
      nativeInFlightRef.current = false;
      if (nativeCommitPendingRef.current || nativeDesiredRef.current !== desiredAtSend) {
        scheduleNativeFlush();
      }
      if (
        nativeStopPendingRef.current &&
        !nativeInFlightRef.current &&
        !nativeCommitPendingRef.current &&
        nativeDesiredRef.current === nativeSessionTextRef.current
      ) {
        resetNativeBuffer();
      }
    }
  };

  const scheduleNativeFlush = () => {
    if (!nativeTypingRef.current) return;
    if (nativeFlushTimeoutRef.current) return;
    nativeFlushTimeoutRef.current = setTimeout(() => {
      nativeFlushTimeoutRef.current = null;
      void flushNative();
    }, NATIVE_FLUSH_INTERVAL_MS);
  };

  const queueNativeText = (text: string, commit = false) => {
    if (!nativeTypingRef.current) return;
    if (!commit && !text) return;
    if (commit) {
      if (!text) {
        nativeDesiredRef.current = "";
        nativeCommitPendingRef.current = false;
        nativeAfterCommitRef.current = null;
        return;
      }
      const finalText = /\s$/.test(text) ? text : `${text} `;
      nativeDesiredRef.current = finalText;
      nativeCommitPendingRef.current = true;
      void flushNative();
      return;
    }
    if (nativeCommitPendingRef.current) {
      nativeAfterCommitRef.current = text;
      return;
    }
    nativeDesiredRef.current = text;
    scheduleNativeFlush();
  };

  const connectAndStart = async () => {
    setError(null);
    setStatus("Creando sesión...");
    
    try {
      const res = await fetch("/api/realtime/session", { method: "POST" });
      if (!res.ok) throw new Error("No se pudo crear la sesión");
      
      const { wsUrl } = await res.json();
      setStatus("Conectando...");
      
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = async () => {
        connectedRef.current = true;
        try {
          await startAudio();
          ws.send(JSON.stringify({ type: "start_recording" }));
          setStatus("Grabando...");
          setRecording(true);
        } catch (err) {
          setError("Microphone permission denied");
          setStatus("Error");
        }
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          
          if (msg.type === "final_transcript") {
            if (msg.text) {
              setFinals((prev) => [...prev, msg.text as string]);
              queueNativeText(msg.text as string, true);
            }
            setStatus("Conectado");
          } else if (msg.type === "status") {
             if (msg.state === "recording") {
                 setRecording(true);
                 setStatus("Grabando...");
             } else if (msg.state === "processing") {
                 setStatus("Procesando transcripción...");
                 setRecording(false);
             } else {
                 setStatus("Conectado");
             }
          } else if (msg.type === "global_hotkey") {
             if (!nativeTypingRef.current) return; // Ignorar atajos globales si el dictado nativo está desactivado
             if (msg.action === "start") {
                 setFinals([]); // Limpiar al iniciar
                 startRecording();
             } else if (msg.action === "stop") {
                 stopAndTranscribe();
             }
          } else if (msg.type === "error") {
             setError(msg.message || "Error");
             setStatus("Error");
          }
        } catch (e) {}
      };

      ws.onclose = () => {
        connectedRef.current = false;
        wsRef.current = null;
        setStatus("Desconectado");
        setRecording(false);
      };

      ws.onerror = () => {
        setError("Error de conexión");
      };
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al conectar");
      setStatus("Error");
    }
  };

  const startRecording = () => {
    if (!connectedRef.current) {
        connectAndStart();
    } else if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "start_recording" }));
    }
  };

  const stopAndTranscribe = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      // Flush any remaining audio
      const pending = pendingSamplesRef.current;
      if (pending.length > 0) {
        const chunk = new Int16Array(pending.length);
        for (let i = 0; i < pending.length; i += 1) {
          chunk[i] = pending[i] as number;
        }
        pending.length = 0;
        wsRef.current.send(JSON.stringify({ type: "audio_chunk", audio: pcm16ToBase64(chunk) }));
      }
      wsRef.current.send(JSON.stringify({ type: "stop_and_transcribe" }));
    }
  };

  const stopSession = useCallback(() => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.close();
    }
    wsRef.current = null;
    connectedRef.current = false;

    workletNodeRef.current?.disconnect();
    workletNodeRef.current = null;

    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;

    audioContextRef.current?.close();
    audioContextRef.current = null;

    pendingSamplesRef.current = [];
    resetNativeBuffer();
    setStatus("Detenido");
    setRecording(false);
  }, [resetNativeBuffer]);

  useEffect(() => {
    return () => stopSession();
  }, [stopSession]);

  useEffect(() => {
    let isKeyDown = false;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.altKey && e.key.toLowerCase() === "i" && !e.repeat) {
        e.preventDefault();
        isKeyDown = true;
        setFinals([]); // Clear the transcript text box
        startRecording();
      }
    };
    const handleKeyUp = (e: KeyboardEvent) => {
      if (isKeyDown && (e.key.toLowerCase() === "i" || e.key === "Alt" || e.key === "AltGraph")) {
        e.preventDefault();
        isKeyDown = false;
        stopAndTranscribe();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, []);

  useEffect(() => {
    nativeTypingRef.current = nativeTyping;
    if (!nativeTyping) resetNativeBuffer();
  }, [nativeTyping, resetNativeBuffer]);

  const startAudio = async () => {
    if (mediaStreamRef.current) return;
    
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
      // Don't send audio unless recording state is true
      if (!recording && connectedRef.current === false) return; // connectedRef implies we are setting up, but the server expects audio
      
      const input = event.data as Float32Array;
      const resampled = resampleFloat32(input, audioContext.sampleRate, TARGET_SAMPLE_RATE);
      const pcm16 = floatToPCM16(resampled);
      
      const pending = pendingSamplesRef.current;
      for (let i = 0; i < pcm16.length; i += 1) {
        pending.push(pcm16[i]);
      }
      if (pending.length > MAX_PENDING_SAMPLES) {
        pending.splice(0, pending.length - MAX_PENDING_SAMPLES);
      }

      while (pending.length >= CHUNK_SAMPLES) {
        const chunk = new Int16Array(CHUNK_SAMPLES);
        for (let i = 0; i < CHUNK_SAMPLES; i += 1) {
          chunk[i] = pending.shift() as number;
        }
        if (connectedRef.current && wsRef.current?.readyState === WebSocket.OPEN) {
           wsRef.current.send(JSON.stringify({
             type: "audio_chunk",
             audio: pcm16ToBase64(chunk)
           }));
        }
      }
    };

    source.connect(workletNode);
    const mute = audioContext.createGain();
    mute.gain.value = 0;
    workletNode.connect(mute).connect(audioContext.destination);
  };

  const statusClass = status === "Error" ? "status-error"
    : status.includes("Escuchando") || status.includes("Grabando") || status.includes("Procesando")
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
          <h1>Voz a Texto Local</h1>
          <p>Transcripción privada con ParaKeet V3 Push-to-Talk</p>
        </div>
        <div className="status-stack">
          <div className={`status ${statusClass}`}>
            <span>Estado</span>
            <strong>{status}</strong>
          </div>
          {showWave && (
            <div className="voice-wave" aria-hidden="true">
              {WAVE_BARS.map((index) => (
                <span key={index} style={{ "--i": index } as CSSProperties} />
              ))}
            </div>
          )}
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
          <button onMouseDown={startRecording} onMouseUp={stopAndTranscribe} onMouseLeave={stopAndTranscribe}>
            Mantener presionado para Iniciar <span className="shortcut">Alt+I</span>
          </button>

          <button onClick={stopSession} disabled={!wsRef.current}>
            Detener Sesión
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
