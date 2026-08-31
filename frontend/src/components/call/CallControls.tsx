import { Mic, MicOff, Pause, Play, PhoneOff } from "lucide-react";
import { formatDuration } from "@/hooks/useCallState";

interface CallControlsProps {
  durationSeconds: number;
  isMuted: boolean;
  isOnHold: boolean;
  onToggleMute: () => void;
  onToggleHold: () => void;
  onHangUp: () => void;
}

export function CallControls({
  durationSeconds,
  isMuted,
  isOnHold,
  onToggleMute,
  onToggleHold,
  onHangUp,
}: CallControlsProps) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-border bg-card px-4 py-3">
      <div className="flex items-center gap-2">
        <span
          className={`h-2 w-2 rounded-full ${
            isOnHold ? "bg-warning" : "bg-success animate-pulse"
          }`}
        />
        <span className="text-sm font-medium">
          {isOnHold ? "En attente" : "Appel en cours"}
        </span>
        <span className="text-sm tabular-nums text-muted-foreground">
          {formatDuration(durationSeconds)}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onToggleMute}
          aria-label={isMuted ? "Réactiver le micro" : "Couper le micro"}
          className={`flex h-9 w-9 items-center justify-center rounded-full border border-border transition ${
            isMuted ? "bg-warning text-white" : "hover:bg-muted"
          }`}
          title={isMuted ? "R\u00e9activer le micro" : "Couper le micro"}
        >
          {isMuted ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
        </button>

        <button
          onClick={onToggleHold}
          aria-label={isOnHold ? "Reprendre l'appel" : "Mettre l'appel en attente"}
          className={`flex h-9 w-9 items-center justify-center rounded-full border border-border transition ${
            isOnHold ? "bg-warning text-white" : "hover:bg-muted"
          }`}
          title={isOnHold ? "Reprendre l'appel" : "Mettre en attente"}
        >
          {isOnHold ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
        </button>

        <button
          onClick={onHangUp}
          aria-label="Raccrocher"
          className="flex h-9 w-9 items-center justify-center rounded-full bg-destructive text-white transition hover:opacity-90"
          title="Raccrocher"
        >
          <PhoneOff className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
