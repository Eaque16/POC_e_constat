import type { SinistreData, VehicleInfo } from "@/types/api";

interface SinistreDataViewProps {
  data: Record<string, unknown> | null;
  infosManquantes: Record<string, unknown>[];
}

const FIELD_LABELS: Record<string, string> = {
  assure_nom: "Nom assur\u00e9",
  assure_telephone: "T\u00e9l\u00e9phone",
  assure_email: "Email",
  assure_adresse: "Adresse",
  date_sinistre: "Date",
  heure_sinistre: "Heure",
  lieu_sinistre: "Lieu",
  type_accident: "Type d'accident",
  description: "Description",
  dommages_assure: "Dommages (assur\u00e9)",
  dommages_tiers: "Dommages (tiers)",
  immobilisation: "V\u00e9hicule immobilis\u00e9",
  besoin_assistance: "Besoin d'assistance",
  tiers_nom: "Nom du tiers",
  tiers_telephone: "T\u00e9l\u00e9phone du tiers",
  tiers_assurance: "Assurance du tiers",
};

function formatVehicle(v: VehicleInfo | undefined | null): string | null {
  if (!v) return null;
  const parts = [v.marque, v.modele, v.immatriculation].filter(Boolean);
  return parts.length > 0 ? parts.join(" - ") : null;
}

export function SinistreDataView({ data, infosManquantes }: SinistreDataViewProps) {
  const d = (data ?? {}) as Partial<SinistreData>;

  const rows: { label: string; value: string }[] = [];
  for (const [key, label] of Object.entries(FIELD_LABELS)) {
    const value = (d as Record<string, unknown>)[key];
    if (value === null || value === undefined || value === "") continue;
    rows.push({ label, value: typeof value === "boolean" ? (value ? "Oui" : "Non") : String(value) });
  }

  const vehiculeAssure = formatVehicle(d.vehicule_assure);
  if (vehiculeAssure) rows.push({ label: "V\u00e9hicule assur\u00e9", value: vehiculeAssure });
  const vehiculeTiers = formatVehicle(d.vehicule_tiers);
  if (vehiculeTiers) rows.push({ label: "V\u00e9hicule tiers", value: vehiculeTiers });

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <div className="rounded-xl border border-border bg-card p-4">
        <h3 className="text-sm font-semibold text-muted-foreground">
          {"Donn\u00e9es extraites par l'IA"}
        </h3>
        {rows.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">
            {"Aucune donn\u00e9e extraite pour l'instant."}
          </p>
        ) : (
          <ul className="mt-2 space-y-1.5">
            {rows.map((row) => (
              <li key={row.label} className="flex justify-between text-sm">
                <span className="text-muted-foreground">{row.label}</span>
                <span className="max-w-[60%] text-right font-medium">{row.value}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-xl border border-border bg-card p-4">
        <h3 className="text-sm font-semibold text-muted-foreground">
          {"Informations manquantes"}
        </h3>
        {infosManquantes.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">
            {"Aucune information manquante signal\u00e9e."}
          </p>
        ) : (
          <ul className="mt-2 space-y-1.5">
            {infosManquantes.map((item, index) => (
              <li key={index} className="flex items-center gap-1.5 text-xs font-medium text-warning">
                {"\u26a0\ufe0f "}
                {typeof item === "string" ? item : JSON.stringify(item)}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
