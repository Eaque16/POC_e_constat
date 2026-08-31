import { useCallback, useRef, useState } from "react";

export function useCallRecording() {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingError, setRecordingError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const start = useCallback(async () => {
    setRecordingError(null);
    chunksRef.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.start(1000);
      setIsRecording(true);
    } catch {
      setRecordingError(
        "Micro inaccessible (permission refusee). L'appel continuera sans enregistrement reel."
      );
      setIsRecording(false);
    }
  }, []);

  const stopAndGetBlob = useCallback((): Promise<Blob | null> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state === "inactive") {
        resolve(chunksRef.current.length ? new Blob(chunksRef.current) : null);
        return;
      }
      recorder.onstop = () => {
        const blob = chunksRef.current.length
          ? new Blob(chunksRef.current, { type: "audio/webm" })
          : null;
        resolve(blob);
      };
      recorder.stop();
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      setIsRecording(false);
    });
  }, []);

  return { isRecording, recordingError, start, stopAndGetBlob };
}
