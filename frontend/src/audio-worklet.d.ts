// Global type declarations for AudioWorklet
declare class AudioWorkletProcessor {
  readonly port: MessagePort;
  constructor();
}

declare function registerProcessor(name: string, processorClass: typeof AudioWorkletProcessor): void;

interface AudioWorkletNode extends AudioNode {
  readonly port: MessagePort;
  constructor(context: BaseAudioContext, name: string, options?: AudioWorkletNodeOptions);
}

interface AudioWorkletNodeOptions {
  numberOfInputs?: number;
  numberOfOutputs?: number;
  outputChannelCount?: number[];
  parameterData?: Record<string, number>;
  processorOptions?: unknown;
}