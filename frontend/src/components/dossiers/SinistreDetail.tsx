import { useState } from "react";
import type { SinistreResponse } from "@/types/api";
import { SinistreDataView } from "@/components/dossiers/SinistreDataView";
import { validateSinistre, rejectSinistre, transmitToEconsta } from "@/services/sinistres";

interface SinistreDetailProps {
  sinistre: SinistreResponse;
  onBack: () => void;
  onUpdated: (updated: SinistreResponse) => void;
}

const AGENT_ID_PLACEHOLDER = "agent-frontend";

export function SinistreDetail({ sinistre, onBack, onUpdated }: SinistreDetailProps) {
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const runAction = async (action: () => Promise<SinistreResponse | unknown>) => {
    setBusy(true);
    setActionError(null);
    try {
      const result = await action();
      if (result && typeof result === "object" && "id" in result) {
        onUpdated(result as SinistreResponse);
      }
    } catch {
      setActionError("Action \u00e9chou\u00e9e. V\u00e9rifie la connexion au backend.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <button
        onClick={onBack}
        className="text-sm font-medium text-primary underline underline-offset-2"
      >
        {"\u2190 Retour \u00e0 la liste"}
      </button>

      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">{sinistre.reference ?? sinistre.id.slice(0, 8)}</h2>
          <span className="rounded-full bg-warning/15 px-2.5 py-0.5 text-xs font-medium text-warning">
            {sinistre.statut}
          </span>
        </div>
        {sinistre.resume && (
          <p className="mt-1 text-sm text-muted-foreground">{sinistre.resume}</p>
        )}
      </div>

      <SinistreDataView
        data={sinistre.donnees_structurees as Record<string, unknown> | null}
        infosManquantes={sinistre.infos_manquantes}
      />

      <div className="rounded-xl border border-border bg-card p-4">
        <h3 className="text-sm font-semibold text-muted-foreground">{"Confiance IA"}</h3>
        <div className="mt-2 flex items-center gap-3">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full bg-primary"
              style={{ width: `${Math.round(sinistre.niveau_confiance * 100)}%` }}
            />
          </div>
          <span className="text-sm font-medium">
            {Math.round(sinistre.niveau_confiance * 100)}%
          </span>
        </div>
      </div>

      {sinistre.econsta_reference && (
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="text-sm font-semibold text-muted-foreground">{"E-consta"}</h3>
          <p className="mt-1 text-sm font-medium">{sinistre.econsta_reference}</p>
        </div>
      )}

      {actionError && <p className="text-sm text-destructive">{actionError}</p>}

      <div className="flex flex-wrap gap-2">
        <button
          disabled={busy}
          onClick={() => runAction(() => validateSinistre(sinistre.id, AGENT_ID_PLACEHOLDER))}
          className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-success transition hover:bg-success/10 disabled:opacity-50"
        >
          {"Valider"}
        </button>
        <button
          disabled={busy}
          onClick={() => runAction(() => rejectSinistre(sinistre.id, AGENT_ID_PLACEHOLDER))}
          className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-destructive transition hover:bg-destructive/10 disabled:opacity-50"
        >
          {"Rejeter"}
        </button>
        <button
          disabled={busy}
          onClick={() => runAction(() => transmitToEconsta(sinistre.id))}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-50"
        >
          {"Transmettre \u00e0 E-consta"}
        </button>
      </div>
    </div>
  );
}
