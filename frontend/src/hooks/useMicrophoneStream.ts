import { useCallback, useEffect, useRef, useState } from "react";
import { TranscriptionSession } from "@/services/transcription";
import type {
  ConnectionMode,
  ConnectionStatus,
  TranscriptTurn,
} from "@/types/transcription";

const CHUNK_INTERVAL_MS = 4000;

interface UseMicrophoneStreamOptions {
  active: boolean;
}

export function useMicrophoneStream({ active }: UseMicrophoneStreamOptions) {
  const [turns, setTurns] = useState<TranscriptTurn[]>([]);
  const [status, setStatus] = useState<ConnectionStatus>("offline");
  const [mode, setMode] = useState<ConnectionMode>("demo");
  const [micError, setMicError] = useState<string | null>(null);

  const sessionRef = useRef<TranscriptionSession | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const stopCapture = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    mediaRecorderRef.current = null;

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (sessionRef.current) {
      sessionRef.current.close();
      sessionRef.current = null;
    }
  }, []);

  const startCapture = useCallback(async () => {
    setMicError(null);
    setTurns([]);

    const session = new TranscriptionSession({
      onStatusChange: (newStatus, newMode) => {
        setStatus(newStatus);
        setMode(newMode);
      },
      onTurn: (turn) => {
        setTurns((prev) => [...prev, turn]);
      },
      onError: (message) => {
        setMicError(message);
      },
    });
    sessionRef.current = session;
    await session.start();
    if (sessionRef.current !== session) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (sessionRef.current !== session) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;

      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0 && sessionRef.current === session) {
          void session.sendAudioChunk(event.data);
        }
      };

      recorder.onerror = () => {
        if (sessionRef.current === session) {
          setMicError("L'enregistrement audio a été interrompu.");
        }
      };

      recorder.start(CHUNK_INTERVAL_MS);
    } catch {
      if (sessionRef.current === session) {
        setMicError(
          "Micro inaccessible (permission refusée ou périphérique indisponible). Mode démo actif sans audio réel."
        );
      }
    }
  }, []);

  useEffect(() => {
    if (active) {
      void startCapture();
    } else {
      stopCapture();
      setStatus("offline");
    }
    return stopCapture;
  }, [active, startCapture, stopCapture]);

  return { turns, status, mode, micError };
}
