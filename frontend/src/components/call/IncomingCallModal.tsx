import { Phone, PhoneOff } from "lucide-react";
import type { MockCaller } from "@/data/mockCall";

interface IncomingCallModalProps {
  caller: MockCaller;
  onAnswer: () => void;
  onDecline: () => void;
}

export function IncomingCallModal({
  caller,
  onAnswer,
  onDecline,
}: IncomingCallModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-6 text-card-foreground shadow-xl">
        <div className="flex flex-col items-center gap-1 text-center">
          <span className="text-sm font-medium text-muted-foreground">
            {"\ud83d\udcde Appel entrant"}
          </span>
          <span className="text-lg font-bold">{caller.name}</span>
          <span className="text-sm text-muted-foreground">{caller.phone}</span>
          {caller.contractNumber && (
            <span className="mt-1 text-xs text-muted-foreground">
              {"Contrat : "}
              {caller.contractNumber}
            </span>
          )}
        </div>

        <div className="mt-6 flex items-center justify-center gap-4">
          <button
            onClick={onDecline}
            className="flex items-center gap-2 rounded-full bg-destructive px-5 py-2.5 text-sm font-medium text-white transition hover:opacity-90"
          >
            <PhoneOff className="h-4 w-4" />
            {"Refuser"}
          </button>
          <button
            onClick={onAnswer}
            className="flex items-center gap-2 rounded-full bg-success px-5 py-2.5 text-sm font-medium text-white transition hover:opacity-90"
          >
            <Phone className="h-4 w-4" />
            {"R\u00e9pondre"}
          </button>
        </div>
      </div>
    </div>
  );
}
