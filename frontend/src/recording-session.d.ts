export const SESSION_PHASE: {
  readonly IDLE: "idle";
  readonly CONNECTING: "connecting";
  readonly READY: "ready";
  readonly RECORDING: "recording";
  readonly PROCESSING: "processing";
  readonly ERROR: "error";
};

export type SessionPhase = (typeof SESSION_PHASE)[keyof typeof SESSION_PHASE];

export type RecordingSessionState = {
  phase: SessionPhase;
  holdActive: boolean;
  socketOpen: boolean;
};

export type RecordingSessionEvent = {
  type:
    | "request_start"
    | "socket_opened"
    | "capture_started"
    | "request_stop"
    | "processing_started"
    | "ready"
    | "transcript_received"
    | "socket_closed"
    | "error";
};

export function createRecordingSessionState(): RecordingSessionState;
export function reduceRecordingSession(
  state: RecordingSessionState,
  event: RecordingSessionEvent
): RecordingSessionState;
export function canStartCapture(state: RecordingSessionState): boolean;
export function shouldCloseSocketAfterOpen(state: RecordingSessionState): boolean;
