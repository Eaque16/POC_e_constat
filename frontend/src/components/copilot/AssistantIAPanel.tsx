import { useState } from "react";
import { analyzeTranscription } from "@/services/sinistres";
import { ApiError } from "@/services/api";
import { SinistreDataView } from "@/components/dossiers/SinistreDataView";
import type { AnalysisResponse } from "@/types/api";

export function AssistantIAPanel() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleAnalyze = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await analyzeTranscription(text.trim());
      setResult(response);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Analyse \u00e9chou\u00e9e (${err.status}) : ${err.message}`);
      } else {
        setError(
          "Backend injoignable - v\u00e9rifie que le serveur tourne sur le port 8000."
        );
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-foreground">
          {"\ud83e\udd16 Assistant IA"}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {
            "Colle ou tape une transcription d'appel (notes, retranscription manuelle) pour que l'IA du backend l'analyse et cr\u00e9e un dossier."
          }
        </p>
      </div>

      <div className="rounded-xl border border-border bg-card p-4">
        <label className="text-xs font-medium text-muted-foreground">
          {"Transcription"}
        </label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          placeholder={
            "Exemple : Bonjour, j'ai eu un accident ce matin a Cocody. C'est un accrochage avec une autre voiture au feu rouge..."
          }
          className="mt-1 w-full resize-y rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
        />

        <div className="mt-3 flex items-center gap-3">
          <button
            onClick={handleAnalyze}
            disabled={loading || !text.trim()}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Analyse en cours..." : "Analyser avec l'IA"}
          </button>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
      </div>

      {result && (
        <div className="space-y-4">
          <div className="rounded-xl border border-border bg-card p-4">
            <h3 className="text-sm font-semibold text-muted-foreground">
              {"Dossier cr\u00e9\u00e9"}
            </h3>
            <p className="mt-1 text-sm font-medium">
              {result.reference ?? result.sinistre_id}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {"Confiance IA : "}
              {Math.round(result.niveau_confiance * 100)}
              {"%"}
            </p>
          </div>

          <SinistreDataView
            data={result.donnees_structurees}
            infosManquantes={result.infos_manquantes}
          />
        </div>
      )}
    </div>
  );
}
