import { useCallback, useEffect, useRef, useState } from "react";

export type VoiceCaptureStatus = "off" | "starting" | "listening" | "speech" | "endpointing" | "error";

interface Options {
  enabled: boolean;
  suspended?: boolean;
  silenceMs?: number;
  maxUtteranceMs?: number;
  onSpeechStart?: () => void;
  onUtterance: (audio: Blob, measurement: SpeechMeasurement) => void | Promise<void>;
}

export interface SpeechMeasurement {
  speechMs: number;
  endpointDelayMs: number;
  capturedAudioMs: number;
  speechStartedAt: number;
  endpointAt: number;
}

interface AcousticFrame { samples: Float32Array; rms: number; peak: number; zcr: number }

function wavBlob(chunks: Float32Array[], sampleRate: number): Blob {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const buffer = new ArrayBuffer(44 + length * 2);
  const view = new DataView(buffer);
  const write = (offset: number, value: string) => [...value].forEach((character, index) => view.setUint8(offset + index, character.charCodeAt(0)));
  write(0, "RIFF"); view.setUint32(4, 36 + length * 2, true); write(8, "WAVE"); write(12, "fmt ");
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  write(36, "data"); view.setUint32(40, length * 2, true);
  let offset = 44;
  for (const chunk of chunks) for (const sample of chunk) { view.setInt16(offset, Math.max(-1, Math.min(1, sample)) * 0x7fff, true); offset += 2; }
  return new Blob([buffer], { type: "audio/wav" });
}

export function useAutomaticSpeechCapture({ enabled, suspended = false, silenceMs = 850, maxUtteranceMs = 20_000, onSpeechStart, onUtterance }: Options) {
  const [status, setStatus] = useState<VoiceCaptureStatus>("off");
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState(0);
  const suspendedRef = useRef(suspended);
  const callbacksRef = useRef({ onSpeechStart, onUtterance });
  const cleanupRef = useRef<() => void>(() => undefined);

  useEffect(() => { suspendedRef.current = suspended; }, [suspended]);
  useEffect(() => { callbacksRef.current = { onSpeechStart, onUtterance }; }, [onSpeechStart, onUtterance]);

  const stop = useCallback(() => { cleanupRef.current(); cleanupRef.current = () => undefined; setStatus("off"); setLevel(0); }, []);

  useEffect(() => {
    if (!enabled) { stop(); return; }
    let cancelled = false;
    setStatus("starting"); setError(null);
    void (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }, video: false });
        const context = new AudioContext({ latencyHint: "interactive", sampleRate: 16_000 });
        await context.audioWorklet.addModule("/pcm-capture-worklet.js?v=voice-gate-2");
        if (cancelled) { stream.getTracks().forEach((track) => track.stop()); void context.close(); return; }
        const source = context.createMediaStreamSource(stream);
        const worklet = new AudioWorkletNode(context, "pcm-capture");
        const silent = context.createGain(); silent.gain.value = 0;
        source.connect(worklet); worklet.connect(silent); silent.connect(context.destination);

        let noiseFloor = 0.006;
        let calibrationFrames = 0;
        const calibrationTarget = 12;
        let speechFrames = 0;
        let voicedFrames = 0;
        let speaking = false;
        let startedAt = 0;
        let lastVoiceAt = 0;
        let utterance: Float32Array[] = [];
        const preRoll: Float32Array[] = [];
        const preRollFrames = Math.max(2, Math.round(context.sampleRate * 0.3 / 2048));

        const finish = () => {
          if (!speaking || utterance.length === 0) return;
          speaking = false; speechFrames = 0; setStatus("endpointing");
          const endpointAt = performance.now();
          const measurement: SpeechMeasurement = {
            speechMs: Math.max(0, lastVoiceAt - startedAt),
            endpointDelayMs: Math.max(0, endpointAt - lastVoiceAt),
            capturedAudioMs: endpointAt - startedAt,
            speechStartedAt: startedAt,
            endpointAt,
          };
          const audio = wavBlob(utterance, context.sampleRate);
          const validSpeech = measurement.speechMs >= 420 && voicedFrames >= 3;
          utterance = [];
          voicedFrames = 0;
          if (!validSpeech) { setStatus("listening"); return; }
          void Promise.resolve(callbacksRef.current.onUtterance(audio, measurement)).finally(() => {
            if (!cancelled && !suspendedRef.current) setStatus("listening");
          });
        };

        worklet.port.onmessage = (event: MessageEvent<AcousticFrame>) => {
          const { samples, rms: value, peak, zcr } = event.data;
          setLevel(Math.min(1, value * 12));
          preRoll.push(samples); while (preRoll.length > preRollFrames) preRoll.shift();
          if (suspendedRef.current) { speaking = false; utterance = []; speechFrames = 0; setStatus("listening"); return; }
          if (calibrationFrames < calibrationTarget && !speaking) {
            noiseFloor = calibrationFrames === 0 ? value : noiseFloor * 0.75 + value * 0.25;
            calibrationFrames += 1;
            setStatus(calibrationFrames >= calibrationTarget ? "listening" : "starting");
            return;
          }
          const threshold = Math.max(0.014, noiseFloor * 3.4);
          const hasVoiceEnergy = value > threshold && peak > Math.max(0.025, threshold * 1.5);
          const voiceLikeSpectrum = zcr >= 0.006 && zcr <= 0.32;
          const voiced = hasVoiceEnergy && voiceLikeSpectrum;
          if (!speaking) {
            if (!voiced && value < threshold * 1.3) noiseFloor = noiseFloor * 0.985 + value * 0.015;
            speechFrames = voiced ? speechFrames + 1 : 0;
            if (speechFrames >= 3) {
              speaking = true; startedAt = performance.now(); lastVoiceAt = startedAt;
              voicedFrames = speechFrames; utterance = [...preRoll]; setStatus("speech"); callbacksRef.current.onSpeechStart?.();
            }
          } else {
            utterance.push(samples);
            if (voiced) { lastVoiceAt = performance.now(); voicedFrames += 1; }
            const now = performance.now();
            if (!voiced && now - lastVoiceAt > silenceMs) finish();
            else if (now - startedAt > maxUtteranceMs) finish();
          }
        };
        setStatus("listening");
        cleanupRef.current = () => {
          cancelled = true; worklet.port.onmessage = null; source.disconnect(); worklet.disconnect(); silent.disconnect();
          stream.getTracks().forEach((track) => track.stop()); void context.close();
        };
      } catch {
        if (!cancelled) { setError("Le mode mains libres ne peut pas accéder au microphone."); setStatus("error"); }
      }
    })();
    return () => { cancelled = true; cleanupRef.current(); cleanupRef.current = () => undefined; };
  }, [enabled, maxUtteranceMs, silenceMs, stop]);

  return { status, error, level, stop };
}
