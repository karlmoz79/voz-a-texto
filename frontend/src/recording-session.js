export const SESSION_PHASE = Object.freeze({
  IDLE: "idle",
  CONNECTING: "connecting",
  READY: "ready",
  RECORDING: "recording",
  PROCESSING: "processing",
  ERROR: "error"
});

export function createRecordingSessionState() {
  return {
    phase: SESSION_PHASE.IDLE,
    holdActive: false,
    socketOpen: false
  };
}

export function reduceRecordingSession(state, event) {
  switch (event.type) {
    case "request_start":
      if (state.phase === SESSION_PHASE.RECORDING) {
        return {
          ...state,
          holdActive: true
        };
      }
      if (state.phase === SESSION_PHASE.PROCESSING) {
        return state;
      }
      return {
        ...state,
        holdActive: true,
        phase: state.socketOpen ? SESSION_PHASE.READY : SESSION_PHASE.CONNECTING
      };

    case "socket_opened":
      return {
        ...state,
        socketOpen: true,
        phase: SESSION_PHASE.READY
      };

    case "capture_started":
      return state.holdActive && state.socketOpen
        ? { ...state, phase: SESSION_PHASE.RECORDING }
        : state;

    case "request_stop":
      return {
        ...state,
        holdActive: false,
        phase:
          state.phase === SESSION_PHASE.RECORDING
            ? SESSION_PHASE.PROCESSING
            : state.phase
      };

    case "processing_started":
      return {
        ...state,
        phase: SESSION_PHASE.PROCESSING
      };

    case "ready":
    case "transcript_received":
      return {
        ...state,
        phase: state.socketOpen ? SESSION_PHASE.READY : SESSION_PHASE.IDLE
      };

    case "socket_closed":
      return {
        phase: SESSION_PHASE.IDLE,
        holdActive: false,
        socketOpen: false
      };

    case "error":
      return {
        ...state,
        holdActive: false,
        phase: SESSION_PHASE.ERROR
      };

    default:
      return state;
  }
}

export function canStartCapture(state) {
  return state.socketOpen && state.holdActive && state.phase === SESSION_PHASE.READY;
}

export function shouldCloseSocketAfterOpen(state) {
  return state.socketOpen && !state.holdActive && state.phase === SESSION_PHASE.READY;
}
