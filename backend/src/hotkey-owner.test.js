import test from "node:test";
import assert from "node:assert/strict";
import { createHotkeyOwnerManager } from "./hotkey-owner.js";

test("assigns the latest eligible session as hotkey owner", () => {
  const ownerManager = createHotkeyOwnerManager();

  ownerManager.setEligible("session-a", true);
  ownerManager.setEligible("session-b", true);

  assert.equal(ownerManager.getOwnerSessionId(), "session-b");
  assert.equal(ownerManager.isOwner("session-b"), true);
});

test("falls back to the previous eligible session when owner disconnects", () => {
  const ownerManager = createHotkeyOwnerManager();

  ownerManager.setEligible("session-a", true);
  ownerManager.setEligible("session-b", true);
  ownerManager.unregister("session-b");

  assert.equal(ownerManager.getOwnerSessionId(), "session-a");
  assert.equal(ownerManager.isOwner("session-a"), true);
});

test("removes ownership when the final eligible session opts out", () => {
  const ownerManager = createHotkeyOwnerManager();

  ownerManager.setEligible("session-a", true);
  ownerManager.setEligible("session-a", false);

  assert.equal(ownerManager.getOwnerSessionId(), null);
  assert.equal(ownerManager.isOwner("session-a"), false);
});
