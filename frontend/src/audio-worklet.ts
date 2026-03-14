class PCMWorkletProcessor extends AudioWorkletProcessor {
  process(inputs: Float32Array[][]) {
    const input = inputs[0];
    if (input && input[0]) {
      const channelData = input[0];
      const buffer = new Float32Array(channelData.length);
      buffer.set(channelData);
      this.port.postMessage(buffer);
    }
    return true;
  }
}

registerProcessor("pcm-worklet", PCMWorkletProcessor);
