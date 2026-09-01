class PcmCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(2048);
    this.offset = 0;
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;
    let sourceOffset = 0;
    while (sourceOffset < channel.length) {
      const count = Math.min(channel.length - sourceOffset, this.buffer.length - this.offset);
      this.buffer.set(channel.subarray(sourceOffset, sourceOffset + count), this.offset);
      this.offset += count;
      sourceOffset += count;
      if (this.offset === this.buffer.length) {
        const completed = this.buffer;
        let energy = 0;
        let peak = 0;
        let crossings = 0;
        let previous = completed[0] || 0;
        for (const sample of completed) {
          energy += sample * sample;
          peak = Math.max(peak, Math.abs(sample));
          if ((sample >= 0) !== (previous >= 0)) crossings += 1;
          previous = sample;
        }
        this.port.postMessage({
          samples: completed,
          rms: Math.sqrt(energy / completed.length),
          peak,
          zcr: crossings / completed.length,
        }, [completed.buffer]);
        this.buffer = new Float32Array(2048);
        this.offset = 0;
      }
    }
    return true;
  }
}

registerProcessor("pcm-capture", PcmCaptureProcessor);
