import { useState } from "react";
import { ivrScript, ivrOptions, type IvrOption } from "@/data/ivrMenu";

interface IVRSimulationProps {
  onComplete: (outcome: IvrOption["outcome"]) => void;
}

export function IVRSimulation({ onComplete }: IVRSimulationProps) {
  const [selected, setSelected] = useState<IvrOption | null>(null);

  const speak = () => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    try {
      const utterance = new SpeechSynthesisUtterance(
        `${ivrScript} ${ivrOptions.map((o) => `${o.key}. ${o.label}`).join(". ")}`
      );
      utterance.lang = "fr-FR";
      window.speechSynthesis.speak(utterance);
    } catch {
      // synthese vocale indisponible : on reste sur l'affichage texte seul
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-foreground/40 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 text-card-foreground shadow-xl">
        <div className="mb-3 flex items-center justify-between">
          <span className="rounded-full bg-warning/15 px-2.5 py-0.5 text-xs font-medium text-warning">
            {"\ud83e\uddea Simulation DEMO - pas de t\u00e9l\u00e9phonie r\u00e9elle"}
          </span>
        </div>

        <p className="text-sm font-medium text-muted-foreground">
          {"\ud83d\udd0a L'IA dit :"}
        </p>
        <p className="mt-1 text-sm">{ivrScript}</p>

        <button
          onClick={speak}
          className="mt-2 text-xs font-medium text-primary underline underline-offset-2"
        >
          {"Lire le message (voix du navigateur)"}
        </button>

        <div className="mt-4 space-y-2">
          {ivrOptions.map((option) => (
            <button
              key={option.key}
              onClick={() => setSelected(option)}
              className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left text-sm transition ${
                selected?.key === option.key
                  ? "border-primary bg-primary/10"
                  : "border-border hover:bg-muted"
              }`}
            >
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                {option.key}
              </span>
              {option.label}
            </button>
          ))}
        </div>

        <button
          disabled={!selected}
          onClick={() => selected && onComplete(selected.outcome)}
          className="mt-5 w-full rounded-lg bg-primary py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {"Continuer"}
        </button>
      </div>
    </div>
  );
}
