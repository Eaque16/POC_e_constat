import type { Dossier } from "@/data/mockDossiers";

interface DossierDetailProps {
  dossier: Dossier;
  onBack: () => void;
}

const timelineSteps = [
  "Appel re\u00e7u",
  "Transcription",
  "Analyse IA",
  "Dossier cr\u00e9\u00e9",
  "Validation agent",
  "Transmission",
  "Cl\u00f4ture",
];

const statusIcon: Record<Dossier["extractedFields"][number]["status"], string> = {
  confirme: "\ud83d\udfe2",
  a_verifier: "\ud83d\udfe1",
  manquant: "\ud83d\udd34",
};

export function DossierDetail({ dossier, onBack }: DossierDetailProps) {
  const missingFields = dossier.extractedFields.filter((f) => f.status === "manquant");

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
          <h2 className="text-lg font-bold">{dossier.reference}</h2>
          <span className="rounded-full bg-warning/15 px-2.5 py-0.5 text-xs font-medium text-warning">
            {dossier.statut}
          </span>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">{dossier.resume}</p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="text-sm font-semibold text-muted-foreground">
            {"Informations assur\u00e9"}
          </h3>
          <dl className="mt-2 space-y-1.5 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">{"Nom"}</dt>
              <dd className="font-medium">{dossier.assure}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">{"T\u00e9l\u00e9phone"}</dt>
              <dd className="font-medium">{dossier.telephone}</dd>
            </div>
          </dl>
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="text-sm font-semibold text-muted-foreground">
            {"Informations du sinistre"}
          </h3>
          <dl className="mt-2 space-y-1.5 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">{"Type"}</dt>
              <dd className="font-medium">{dossier.type}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">{"Date"}</dt>
              <dd className="font-medium">{dossier.date}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">{"Lieu"}</dt>
              <dd className="font-medium">{dossier.lieu}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">{"Agent"}</dt>
              <dd className="font-medium">{dossier.agent}</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-4">
        <h3 className="text-sm font-semibold text-muted-foreground">
          {"Transcription"}
        </h3>
        <div className="mt-2 max-h-64 space-y-2 overflow-y-auto">
          {dossier.transcription.map((line, index) => (
            <div key={index} className="text-sm">
              <span
                className={`font-semibold ${
                  line.speaker === "agent" ? "text-primary" : "text-foreground"
                }`}
              >
                {line.speaker === "agent" ? "AGENT" : "ASSURE"}
              </span>
              <p className="mt-0.5 text-foreground/90">{line.text}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="text-sm font-semibold text-muted-foreground">
            {"Informations extraites"}
          </h3>
          <ul className="mt-2 space-y-1.5">
            {dossier.extractedFields.map((field) => (
              <li key={field.label} className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{field.label}</span>
                <span className="flex items-center gap-1.5 font-medium">
                  {statusIcon[field.status]}
                  {field.value ?? "-"}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="text-sm font-semibold text-muted-foreground">
            {"Informations manquantes"}
          </h3>
          {missingFields.length === 0 ? (
            <p className="mt-2 text-sm text-muted-foreground">
              {"Aucune information manquante."}
            </p>
          ) : (
            <ul className="mt-2 space-y-1.5">
              {missingFields.map((field) => (
                <li
                  key={field.label}
                  className="flex items-center gap-1.5 text-xs font-medium text-warning"
                >
                  {"\u26a0\ufe0f "}
                  {field.label}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-4">
        <h3 className="text-sm font-semibold text-muted-foreground">
          {"Confiance IA"}
        </h3>
        <div className="mt-2 flex items-center gap-3">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full bg-primary"
              style={{ width: `${dossier.confiance}%` }}
            />
          </div>
          <span className="text-sm font-medium">{dossier.confiance}%</span>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-4">
        <h3 className="text-sm font-semibold text-muted-foreground">
          {"Historique"}
        </h3>
        <ol className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          {timelineSteps.map((step, index) => (
            <li key={step} className="flex items-center gap-2">
              <span className="rounded-full bg-muted px-2.5 py-1 font-medium text-muted-foreground">
                {step}
              </span>
              {index < timelineSteps.length - 1 && (
                <span className="text-muted-foreground">{"\u2192"}</span>
              )}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
