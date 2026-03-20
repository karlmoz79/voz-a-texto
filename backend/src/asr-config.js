export const DEFAULT_ASR_MODEL_ID = "nvidia/stt_es_fastconformer_hybrid_large_pc";
export const DEFAULT_ASR_MAX_AUDIO_SEC = 30;
export const PCM16_BYTES_PER_SEC = 16000 * 2;

function readNonEmptyString(value) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function readPositiveNumber(value, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return parsed;
}

export function resolveAsrConfig(env = process.env) {
  const modelIdFromCurrentEnv = readNonEmptyString(env.ASR_MODEL_ID);
  const modelIdFromLegacyEnv = readNonEmptyString(env.PARAKEET_MODEL_PATH);
  const maxAudioFromCurrentEnv = env.ASR_MAX_AUDIO_SEC;
  const maxAudioFromLegacyEnv = env.PARAKEET_MAX_AUDIO_SEC;

  return {
    modelId: modelIdFromCurrentEnv || modelIdFromLegacyEnv || DEFAULT_ASR_MODEL_ID,
    maxAudioSec: readPositiveNumber(
      maxAudioFromCurrentEnv ?? maxAudioFromLegacyEnv,
      DEFAULT_ASR_MAX_AUDIO_SEC
    ),
    usedLegacyModelEnv: !modelIdFromCurrentEnv && Boolean(modelIdFromLegacyEnv),
    usedLegacyMaxAudioEnv: maxAudioFromCurrentEnv == null && maxAudioFromLegacyEnv != null
  };
}
