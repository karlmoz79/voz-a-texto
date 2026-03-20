export function createHotkeyOwnerManager() {
  const eligibleSessionIds = [];
  let ownerSessionId = null;

  const removeSession = (sessionId) => {
    const sessionIndex = eligibleSessionIds.indexOf(sessionId);
    if (sessionIndex !== -1) {
      eligibleSessionIds.splice(sessionIndex, 1);
    }
  };

  const finalizeOwnerChange = (nextOwnerSessionId) => {
    const previousOwnerId = ownerSessionId;
    ownerSessionId = nextOwnerSessionId;
    return {
      previousOwnerId,
      nextOwnerId: ownerSessionId,
      changed: previousOwnerId !== ownerSessionId
    };
  };

  return {
    setEligible(sessionId, wantsControl) {
      removeSession(sessionId);

      if (wantsControl) {
        eligibleSessionIds.push(sessionId);
        return finalizeOwnerChange(sessionId);
      }

      if (ownerSessionId === sessionId) {
        return finalizeOwnerChange(eligibleSessionIds.at(-1) || null);
      }

      return finalizeOwnerChange(ownerSessionId);
    },

    unregister(sessionId) {
      removeSession(sessionId);

      if (ownerSessionId === sessionId) {
        return finalizeOwnerChange(eligibleSessionIds.at(-1) || null);
      }

      return finalizeOwnerChange(ownerSessionId);
    },

    getOwnerSessionId() {
      return ownerSessionId;
    },

    isOwner(sessionId) {
      return ownerSessionId !== null && ownerSessionId === sessionId;
    }
  };
}
