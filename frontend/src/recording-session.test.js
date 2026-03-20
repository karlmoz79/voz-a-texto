import test from "node:test";
import assert from "node:assert/strict";
import {
  SESSION_PHASE,
  canStartCapture,
  createRecordingSessionState,
  reduceRecordingSession,
  shouldCloseSocketAfterOpen
} from "./recording-session.js";

test("does not enter recording when the user releases before the socket opens", () => {
  let state = createRecordingSessionState();

  state = reduceRecordingSession(state, { type: "request_start" });
  state = reduceRecordingSession(state, { type: "request_stop" });
  state = reduceRecordingSession(state, { type: "socket_opened" });

  assert.equal(shouldCloseSocketAfterOpen(state), true);
  assert.equal(canStartCapture(state), false);
  assert.equal(state.phase, SESSION_PHASE.READY);
});

test("moves to processing only after an active recording is stopped", () => {
  let state = createRecordingSessionState();

  state = reduceRecordingSession(state, { type: "request_start" });
  state = reduceRecordingSession(state, { type: "socket_opened" });
  state = reduceRecordingSession(state, { type: "capture_started" });
  state = reduceRecordingSession(state, { type: "request_stop" });

  assert.equal(state.phase, SESSION_PHASE.PROCESSING);
  assert.equal(state.holdActive, false);
});

test("keeps recording state stable when start is triggered twice", () => {
  let state = createRecordingSessionState();

  state = reduceRecordingSession(state, { type: "request_start" });
  state = reduceRecordingSession(state, { type: "socket_opened" });
  state = reduceRecordingSession(state, { type: "capture_started" });
  state = reduceRecordingSession(state, { type: "request_start" });

  assert.equal(state.phase, SESSION_PHASE.RECORDING);
  assert.equal(state.holdActive, true);
});
