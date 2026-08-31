import type { ConnectionStatus } from "@/types/transcription";

interface LiveCallStatusProps {
  status: ConnectionStatus;
  micError: string | null;
}

const statusConfig: Record<ConnectionStatus, { label: string; dotClass: string }> = {
  connecting: { label: "Connexion...", dotClass: "bg-warning animate-pulse" },
  listening: { label: "A l'ecoute", dotClass: "bg-success animate-pulse" },
  processing: { label: "Traitement...", dotClass: "bg-primary animate-pulse" },
  reconnecting: { label: "Reconnexion...", dotClass: "bg-warning animate-pulse" },
  offline: { label: "Hors ligne", dotClass: "bg-muted-foreground" },
};

export function LiveCallStatus({ status, micError }: LiveCallStatusProps) {
  const config = statusConfig[status];

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className={`h-2 w-2 rounded-full ${config.dotClass}`} />
      <span className="text-muted-foreground">{config.label}</span>
      {micError && (
        <span className="text-warning">{`- ${micError}`}</span>
      )}
    </div>
  );
}
