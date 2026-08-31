import type { TranscriptTurn, ConnectionMode } from "@/types/transcription";

interface LiveTranscriptProps {
  turns: TranscriptTurn[];
  mode: ConnectionMode;
  isListening: boolean;
}

const modeLabels: Record<ConnectionMode, string> = {
  websocket: "Flux temps r\u00e9el (WebSocket)",
  rest: "Flux par segments (REST)",
  demo: "Mode DEMO - pas de flux r\u00e9el",
};

export function LiveTranscript({ turns, mode, isListening }: LiveTranscriptProps) {
  return (
    <div className="flex h-full flex-col rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-muted-foreground">
          {"Conversation live"}
        </h3>
        <span className="text-xs text-muted-foreground">{modeLabels[mode]}</span>
      </div>

      <div className="mt-3 flex-1 space-y-3 overflow-y-auto">
        {turns.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {"En attente de la premi\u00e8re prise de parole..."}
          </p>
        )}

        {turns.map((turn) => (
          <div key={turn.id} className="text-sm">
            <span
              className={`font-semibold ${
                turn.speaker === "agent" ? "text-primary" : "text-foreground"
              }`}
            >
              {turn.speaker === "agent" ? "AGENT" : "ASSURE"}
            </span>
            <p className="mt-0.5 text-foreground/90">{turn.text}</p>
          </div>
        ))}
      </div>

      {isListening && (
        <p className="mt-2 text-xs text-muted-foreground">
          {"Transcription en cours..."}
        </p>
      )}
    </div>
  );
}
