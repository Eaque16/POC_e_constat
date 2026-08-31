import { useCallback, useEffect, useRef, useState } from "react";

export type CallStatus = "idle" | "incoming" | "active" | "ended";

export interface CallState {
  status: CallStatus;
  isMuted: boolean;
  isOnHold: boolean;
  durationSeconds: number;
}

const initialState: CallState = {
  status: "idle",
  isMuted: false,
  isOnHold: false,
  durationSeconds: 0,
};

export function useCallState() {
  const [state, setState] = useState<CallState>(initialState);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (state.status === "active" && !state.isOnHold) {
      timerRef.current = setInterval(() => {
        setState((s) => ({ ...s, durationSeconds: s.durationSeconds + 1 }));
      }, 1000);
    } else {
      clearTimer();
    }
    return clearTimer;
  }, [state.status, state.isOnHold, clearTimer]);

  const simulateIncomingCall = useCallback(() => {
    setState({ ...initialState, status: "incoming" });
  }, []);

  const answer = useCallback(() => {
    setState((s) => ({ ...s, status: "active" }));
  }, []);

  const decline = useCallback(() => {
    setState(initialState);
  }, []);

  const toggleMute = useCallback(() => {
    setState((s) => ({ ...s, isMuted: !s.isMuted }));
  }, []);

  const toggleHold = useCallback(() => {
    setState((s) => ({ ...s, isOnHold: !s.isOnHold }));
  }, []);

  const hangUp = useCallback(() => {
    setState((s) => ({ ...s, status: "ended" }));
  }, []);

  const reset = useCallback(() => {
    setState(initialState);
  }, []);

  return {
    state,
    simulateIncomingCall,
    answer,
    decline,
    toggleMute,
    toggleHold,
    hangUp,
    reset,
  };
}

export function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, "0");
  const seconds = (totalSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}
