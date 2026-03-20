import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import {
  SESSION_PHASE,
  canStartCapture,
  createRecordingSessionState,
  reduceRecordingSession,
  shouldCloseSocketAfterOpen,
  type RecordingSessionState,
  type SessionPhase
} from "./recording-session.js";

const TARGET_SAMPLE_RATE = 16000;
const CHUNK_SAMPLES = 2560;
const NATIVE_FLUSH_INTERVAL_MS = 16;
const MAX_PENDING_SAMPLES = Math.floor(TARGET_SAMPLE_RATE * 0.5);
const WAVE_BARS = Array.from({ length: 13 }, (_, index) => index);

type BackendStatus = "idle" | "loading_model" | "ready";
type SessionEventType =
  | "request_start"
  | "socket_opened"
  | "capture_started"
  | "request_stop"
  | "processing_started"
  | "ready"
  | "transcript_received"
  | "socket_closed"
  | "error";

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
    const sample = Math.max(-1, Math.min(1, input[i]));
    output[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
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

function getStatusLabel(phase: SessionPhase, backendStatus: BackendStatus) {
  if (phase === SESSION_PHASE.ERROR) {
    return "Error";
  }
  if (phase === SESSION_PHASE.CONNECTING) {
    return backendStatus === "loading_model"
      ? "Conectando y cargando modelo..."
      : "Conectando...";
  }
  if (phase === SESSION_PHASE.RECORDING) {
    return "Grabando...";
  }
  if (phase === SESSION_PHASE.PROCESSING) {
    return "Procesando transcripcion...";
  }
  if (backendStatus === "loading_model") {
    return "Cargando modelo...";
  }
  if (phase === SESSION_PHASE.READY) {
    return "Listo";
  }
  return "Inactivo";
}

export default function App() {
  type RecordingTrigger = "button" | "hotkey";

  const [sessionState, setSessionState] = useState<RecordingSessionState>(() =>
    createRecordingSessionState()
  );
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("idle");
  const [finals, setFinals] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [nativeTyping, setNativeTyping] = useState(true);
  const [hotkeyOwner, setHotkeyOwner] = useState(false);

  const sessionStateRef = useRef(sessionState);
  const wsRef = useRef<WebSocket | null>(null);
  const socketStateRef = useRef<"closed" | "connecting" | "open">("closed");
  const sessionIdRef = useRef<string | null>(null);
  const connectPromiseRef = useRef<Promise<void> | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const pendingSamplesRef = useRef<number[]>([]);
  const captureActiveRef = useRef(false);
  const autoStopRequestedRef = useRef(false);
  const totalCapturedSamplesRef = useRef(0);
  const maxAudioSecRef = useRef(30);
  const serverRecordingRef = useRef(false);
  const startRecordingRef = useRef<(trigger?: RecordingTrigger) => void>(() => undefined);
  const stopAndTranscribeRef = useRef<() => void>(() => undefined);

  const nativeTypingRef = useRef(nativeTyping);
  const nativeDesiredRef = useRef("");
  const nativeSessionTextRef = useRef("");
  const nativeInFlightRef = useRef(false);
  const nativeCommitPendingRef = useRef(false);
  const nativeAfterCommitRef = useRef<string | null>(null);
  const nativeFlushTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const mergedTranscript = useMemo(() => finals.join(" "), [finals]);
  const showWave = sessionState.phase === SESSION_PHASE.RECORDING;
  const statusLabel = getStatusLabel(sessionState.phase, backendStatus);

  const replaceSessionState = (nextState: RecordingSessionState) => {
    sessionStateRef.current = nextState;
    setSessionState(nextState);
  };

  const applySessionEvent = (type: SessionEventType) => {
    const nextState = reduceRecordingSession(sessionStateRef.current, { type });
    replaceSessionState(nextState);
    return nextState;
  };

  async function sendNativeText(
    text: string,
    backspaces = 0,
    appendSpace = false,
    delayMs = 1
  ) {
    try {
      if (!text && backspaces <= 0) return true;

      const response = await fetch("/api/native/type", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, backspaces, appendSpace, delayMs })
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        setError(data?.error || "No se pudo enviar texto a la ventana activa");
        return false;
      }

      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al enviar texto a la ventana activa");
      return false;
    }
  }

  function resetNativeBuffer() {
    nativeDesiredRef.current = "";
    nativeSessionTextRef.current = "";
    nativeCommitPendingRef.current = false;
    nativeInFlightRef.current = false;
    nativeAfterCommitRef.current = null;

    if (nativeFlushTimeoutRef.current) {
      clearTimeout(nativeFlushTimeoutRef.current);
      nativeFlushTimeoutRef.current = null;
    }
  }

  function scheduleNativeFlush() {
    if (!nativeTypingRef.current || nativeFlushTimeoutRef.current) return;

    nativeFlushTimeoutRef.current = setTimeout(() => {
      nativeFlushTimeoutRef.current = null;
      void flushNative();
    }, NATIVE_FLUSH_INTERVAL_MS);
  }

  async function flushNative() {
    if (!nativeTypingRef.current || nativeInFlightRef.current) return;

    const desired = nativeDesiredRef.current;
    const current = nativeSessionTextRef.current;
    const commitPending = nativeCommitPendingRef.current;

    if (desired === current && !commitPending) return;

    const { append, nextTyped } = appendOnlyDelta(current, desired);
    if (!append) {
      if (commitPending) {
        nativeCommitPendingRef.current = false;
        if (nativeAfterCommitRef.current) {
          nativeDesiredRef.current = nativeAfterCommitRef.current;
          nativeAfterCommitRef.current = null;
          scheduleNativeFlush();
        }
      }
      return;
    }

    nativeInFlightRef.current = true;
    const desiredAtSend = desired;

    try {
      const ok = await sendNativeText(append, 0, false, 1);
      if (ok) {
        nativeSessionTextRef.current = nextTyped;
        if (commitPending) {
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
    }
  }

  function queueNativeText(text: string, commit = false) {
    if (!nativeTypingRef.current) return;
    if (!commit && !text) return;

    if (commit) {
      if (!text) {
        nativeDesiredRef.current = "";
        nativeCommitPendingRef.current = false;
        nativeAfterCommitRef.current = null;
        return;
      }

      nativeDesiredRef.current = /\s$/.test(text) ? text : `${text} `;
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
  }

  async function stopAudioCapture() {
    captureActiveRef.current = false;
    autoStopRequestedRef.current = false;
    pendingSamplesRef.current = [];
    totalCapturedSamplesRef.current = 0;

    workletNodeRef.current?.disconnect();
    workletNodeRef.current = null;

    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;

    const audioContext = audioContextRef.current;
    audioContextRef.current = null;

    if (audioContext) {
      await audioContext.close().catch(() => undefined);
    }
  }

  function flushPendingAudio() {
    const pending = pendingSamplesRef.current;
    const ws = wsRef.current;

    if (!pending.length) {
      return 0;
    }

    const chunk = new Int16Array(pending.length);
    for (let i = 0; i < pending.length; i += 1) {
      chunk[i] = pending[i] as number;
    }
    pending.length = 0;

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "audio_chunk", audio: pcm16ToBase64(chunk) }));
    }

    return chunk.length;
  }

  async function startAudioCapture() {
    if (captureActiveRef.current) return;

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    let audioContext: AudioContext | null = null;

    try {
      audioContext = new AudioContext();
      await audioContext.audioWorklet.addModule(new URL("./audio-worklet.ts", import.meta.url));
      if (audioContext.state === "suspended") {
        await audioContext.resume().catch(() => undefined);
      }

      const source = audioContext.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(audioContext, "pcm-worklet");
      const mute = audioContext.createGain();
      mute.gain.value = 0;

      pendingSamplesRef.current = [];
      totalCapturedSamplesRef.current = 0;
      autoStopRequestedRef.current = false;

      workletNode.port.onmessage = (event) => {
        if (
          !captureActiveRef.current ||
          autoStopRequestedRef.current ||
          socketStateRef.current !== "open"
        ) {
          return;
        }

        const ws = wsRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) return;

        const input = event.data as Float32Array;
        const resampled = resampleFloat32(input, audioContext.sampleRate, TARGET_SAMPLE_RATE);
        const pcm16 = floatToPCM16(resampled);
        const maxSamples = Math.max(1, Math.floor(maxAudioSecRef.current * TARGET_SAMPLE_RATE));
        const remainingSamples = Math.max(0, maxSamples - totalCapturedSamplesRef.current);

        if (remainingSamples === 0) {
          autoStopRequestedRef.current = true;
          void stopAndTranscribeRef.current();
          return;
        }

        const limitedPcm16 =
          pcm16.length > remainingSamples
            ? pcm16.subarray(0, remainingSamples)
            : pcm16;

        totalCapturedSamplesRef.current += limitedPcm16.length;

        const pending = pendingSamplesRef.current;
        for (let i = 0; i < limitedPcm16.length; i += 1) {
          pending.push(limitedPcm16[i]);
        }
        if (pending.length > MAX_PENDING_SAMPLES) {
          pending.splice(0, pending.length - MAX_PENDING_SAMPLES);
        }

        while (pending.length >= CHUNK_SAMPLES) {
          const chunk = new Int16Array(CHUNK_SAMPLES);
          for (let i = 0; i < CHUNK_SAMPLES; i += 1) {
            chunk[i] = pending.shift() as number;
          }

          ws.send(JSON.stringify({ type: "audio_chunk", audio: pcm16ToBase64(chunk) }));
        }

        if (totalCapturedSamplesRef.current >= maxSamples) {
          autoStopRequestedRef.current = true;
          void stopAndTranscribeRef.current();
        }
      };

      source.connect(workletNode);
      workletNode.connect(mute).connect(audioContext.destination);

      mediaStreamRef.current = stream;
      audioContextRef.current = audioContext;
      workletNodeRef.current = workletNode;
      captureActiveRef.current = true;
    } catch (err) {
      stream.getTracks().forEach((track) => track.stop());
      if (audioContext) {
        await audioContext.close().catch(() => undefined);
      }
      throw err;
    }
  }

  function handleSocketClosed() {
    if (socketStateRef.current === "closed" && wsRef.current === null) {
      return;
    }

    wsRef.current = null;
    socketStateRef.current = "closed";
    sessionIdRef.current = null;
    connectPromiseRef.current = null;
    serverRecordingRef.current = false;

    setHotkeyOwner(false);
    setBackendStatus("idle");
    replaceSessionState(reduceRecordingSession(sessionStateRef.current, { type: "socket_closed" }));

    void stopAudioCapture();
  }

  function closeRealtimeSocket(reason = "client_closed") {
    const ws = wsRef.current;

    if (!ws) {
      handleSocketClosed();
      return;
    }

    if (ws.readyState === WebSocket.OPEN) {
      try {
        ws.close(1000, reason);
      } catch (_err) {
        handleSocketClosed();
      }
      return;
    }

    if (ws.readyState === WebSocket.CONNECTING) {
      try {
        ws.close();
      } catch (_err) {
        handleSocketClosed();
      }
      return;
    }

    handleSocketClosed();
  }

  function handleBackendStatusMessage(nextStatus: string) {
    if (nextStatus === "loading_model") {
      setBackendStatus("loading_model");
      return;
    }

    if (nextStatus === "ready") {
      setBackendStatus("ready");
      applySessionEvent("ready");
      return;
    }

    if (nextStatus === "recording") {
      applySessionEvent("capture_started");
      return;
    }

    if (nextStatus === "processing") {
      applySessionEvent("processing_started");
      return;
    }

    if (nextStatus === "idle_timeout") {
      setError("La sesion se cerro por inactividad.");
    }
  }

  function beginCaptureSession() {
    if (!canStartCapture(sessionStateRef.current)) return;
    if (captureActiveRef.current) return;
    if (socketStateRef.current !== "open") return;

    void (async () => {
      try {
        await startAudioCapture();

        if (!sessionStateRef.current.holdActive || socketStateRef.current !== "open") {
          await stopAudioCapture();
          closeRealtimeSocket("capture_cancelled");
          return;
        }

        const ws = wsRef.current;
        if (!ws || ws.readyState !== WebSocket.OPEN) {
          await stopAudioCapture();
          return;
        }

        ws.send(JSON.stringify({ type: "start_recording" }));
        serverRecordingRef.current = true;
        setError(null);
        applySessionEvent("capture_started");
      } catch (err) {
        await stopAudioCapture();
        closeRealtimeSocket("capture_failed");
        setError(err instanceof Error ? err.message : "No se pudo acceder al microfono");
        applySessionEvent("error");
      }
    })();
  }

  async function connectRealtimeSession() {
    if (socketStateRef.current === "open") return;
    if (connectPromiseRef.current) return connectPromiseRef.current;

    socketStateRef.current = "connecting";

    const promise = (async () => {
      const response = await fetch("/api/realtime/session", { method: "POST" });
      if (!response.ok) {
        throw new Error("No se pudo crear la sesion");
      }

      const { wsUrl, sessionId, maxAudioSec } = (await response.json()) as {
        wsUrl: string;
        sessionId: string;
        maxAudioSec?: number;
      };

      sessionIdRef.current = sessionId;
      if (Number.isFinite(maxAudioSec) && (maxAudioSec as number) > 0) {
        maxAudioSecRef.current = Math.floor(maxAudioSec as number);
      }

      await new Promise<void>((resolve, reject) => {
        const ws = new WebSocket(wsUrl);
        let opened = false;
        let settled = false;

        const fail = (connectionError: Error) => {
          if (settled) return;
          settled = true;
          reject(connectionError);
        };

        const succeed = () => {
          if (settled) return;
          settled = true;
          resolve();
        };

        wsRef.current = ws;

        ws.onopen = () => {
          opened = true;
          socketStateRef.current = "open";
          ws.send(
            JSON.stringify({
              type: "register_client",
              sessionId,
              wantsHotkeyControl: true
            })
          );

          const nextState = applySessionEvent("socket_opened");
          succeed();

          if (shouldCloseSocketAfterOpen(nextState)) {
            closeRealtimeSocket("cancelled_before_capture");
            return;
          }

          if (canStartCapture(nextState)) {
            beginCaptureSession();
          }
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);

            if (message.type === "final_transcript") {
              const text = typeof message.text === "string" ? message.text.trim() : "";
              if (text) {
                setFinals((current) => [...current, text]);
                queueNativeText(text, true);
              }
              setBackendStatus("ready");
              setError(null);
              applySessionEvent("transcript_received");
              return;
            }

            if (message.type === "status" && typeof message.state === "string") {
              handleBackendStatusMessage(message.state);
              return;
            }

            if (message.type === "hotkey_owner") {
              setHotkeyOwner(Boolean(message.isOwner));
              return;
            }

            if (message.type === "global_hotkey") {
              if (message.action === "start") {
                startRecordingRef.current("hotkey");
                return;
              }
              if (message.action === "stop") {
                stopAndTranscribeRef.current();
              }
              return;
            }

            if (message.type === "error") {
              setError(message.message || "Error");
              applySessionEvent("error");
            }
          } catch (_err) {}
        };

        ws.onerror = () => {
          setError("Error de conexion");
          if (!opened) {
            fail(new Error("Error de conexion"));
          }
        };

        ws.onclose = () => {
          const shouldReject = !opened;
          handleSocketClosed();
          if (shouldReject) {
            fail(new Error("La sesion se cerro antes de abrirse"));
          }
        };
      });
    })()
      .catch(async (err) => {
        await stopAudioCapture();
        handleSocketClosed();
        applySessionEvent("error");
        setError(err instanceof Error ? err.message : "No se pudo crear la sesion");
        throw err;
      })
      .finally(() => {
        connectPromiseRef.current = null;
      });

    connectPromiseRef.current = promise;
    return promise;
  }

  function startRecording(trigger: RecordingTrigger = "button") {
    setError(null);
    if (trigger === "hotkey") {
      setFinals([]);
    }
    const nextState = applySessionEvent("request_start");

    if (socketStateRef.current === "open") {
      if (canStartCapture(nextState)) {
        beginCaptureSession();
      }
      return;
    }

    if (socketStateRef.current !== "connecting") {
      void connectRealtimeSession();
    }
  }

  async function stopAndTranscribe() {
    const currentState = sessionStateRef.current;

    if (
      !currentState.holdActive &&
      !serverRecordingRef.current &&
      currentState.phase !== SESSION_PHASE.RECORDING &&
      currentState.phase !== SESSION_PHASE.CONNECTING
    ) {
      return;
    }

    applySessionEvent("request_stop");

    if (socketStateRef.current === "connecting") {
      return;
    }

    const hadAudio = totalCapturedSamplesRef.current > 0 || pendingSamplesRef.current.length > 0;
    flushPendingAudio();
    await stopAudioCapture();

    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN && serverRecordingRef.current) {
      ws.send(JSON.stringify({ type: "stop_and_transcribe" }));
      serverRecordingRef.current = false;

      if (hadAudio) {
        applySessionEvent("processing_started");
      } else {
        applySessionEvent("ready");
      }
    }
  }

  async function stopSession() {
    serverRecordingRef.current = false;
    resetNativeBuffer();
    await stopAudioCapture();
    closeRealtimeSocket("client_stopped");
  }

  function exportTranscript() {
    const blob = new Blob([mergedTranscript], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "transcript.txt";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  startRecordingRef.current = startRecording;
  stopAndTranscribeRef.current = () => {
    void stopAndTranscribe();
  };

  useEffect(() => {
    nativeTypingRef.current = nativeTyping;
    if (!nativeTyping) {
      resetNativeBuffer();
    }
  }, [nativeTyping]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.altKey && event.key.toLowerCase() === "i" && !event.repeat) {
        event.preventDefault();
        startRecordingRef.current("hotkey");
      }
    };

    const handleKeyUp = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "i" || event.key === "Alt" || event.key === "AltGraph") {
        event.preventDefault();
        stopAndTranscribeRef.current();
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
    return () => {
      serverRecordingRef.current = false;
      resetNativeBuffer();
      void stopAudioCapture();

      const ws = wsRef.current;
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
        try {
          ws.close(1000, "component_unmount");
        } catch (_err) {}
      }
    };
  }, []);

  const statusClass =
    sessionState.phase === SESSION_PHASE.ERROR
      ? "status-error"
      : sessionState.phase === SESSION_PHASE.RECORDING ||
          sessionState.phase === SESSION_PHASE.PROCESSING ||
          backendStatus === "loading_model"
        ? "status-listening"
        : "";

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Voz a Texto Local</h1>
          <p>Fast Conformer ES por defecto, con Parakeet disponible por configuracion.</p>
        </div>
        <div className="status-stack">
          <div className={`status ${statusClass}`}>
            <span>Estado</span>
            <strong>{statusLabel}</strong>
          </div>
          <div className="stack-note">
            {hotkeyOwner
              ? "Alt+I global activo en esta pestana"
              : "Alt+I global no controlado por esta pestana"}
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
        <div className="session-meta">
          <span>Modelo por defecto</span>
          <strong>Fast Conformer ES</strong>
          <small>Configurable via `ASR_MODEL_ID` para usar Parakeet.</small>
        </div>

        <label className="toggle">
          <span>Dictado nativo</span>
          <input
            type="checkbox"
            checked={nativeTyping}
            onChange={(event) => setNativeTyping(event.target.checked)}
          />
        </label>

        <div className="buttons">
          <button
            onPointerDown={() => startRecording("button")}
            onPointerUp={() => {
              void stopAndTranscribe();
            }}
            onPointerCancel={() => {
              void stopAndTranscribe();
            }}
            onPointerLeave={() => {
              void stopAndTranscribe();
            }}
          >
            Mantener presionado para grabar <span className="shortcut">Alt+I</span>
          </button>

          <button
            onClick={() => {
              void stopSession();
            }}
            disabled={!sessionState.socketOpen && sessionState.phase !== SESSION_PHASE.CONNECTING}
          >
            Detener sesion
          </button>

          <button onClick={exportTranscript} disabled={!mergedTranscript.trim()}>
            Exportar texto
          </button>
        </div>
      </section>

      {error && <div className="error">{error}</div>}

      <section className="transcript">
        <h2>Transcripcion</h2>
        <div className="final">{mergedTranscript || "Tu texto aparecera aqui cuando termines de dictar."}</div>
      </section>
    </div>
  );
}
