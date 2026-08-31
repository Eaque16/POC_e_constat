import { useMemo, useState } from "react";
import type { Dossier, DossierStatus } from "@/data/mockDossiers";

interface DossierListProps {
  dossiers: Dossier[];
  onSelect: (reference: string) => void;
}

const filters: { key: "Tous" | DossierStatus; label: string }[] = [
  { key: "Tous", label: "Tous" },
  { key: "Nouveau", label: "Nouveaux" },
  { key: "En cours", label: "En cours" },
  { key: "A verifier", label: "A v\u00e9rifier" },
  { key: "Valide", label: "Valid\u00e9s" },
  { key: "Transmis", label: "Transmis" },
  { key: "Cloture", label: "Cl\u00f4tur\u00e9s" },
];

const statusStyles: Record<DossierStatus, string> = {
  Nouveau: "bg-primary/10 text-primary",
  "En cours": "bg-primary/10 text-primary",
  "A verifier": "bg-warning/15 text-warning",
  Valide: "bg-success/15 text-success",
  Transmis: "bg-success/15 text-success",
  Cloture: "bg-muted text-muted-foreground",
};

export function DossierList({ dossiers, onSelect }: DossierListProps) {
  const [activeFilter, setActiveFilter] = useState<"Tous" | DossierStatus>("Tous");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    return dossiers.filter((d) => {
      const matchesFilter = activeFilter === "Tous" || d.statut === activeFilter;
      const q = search.trim().toLowerCase();
      const matchesSearch =
        q.length === 0 ||
        d.reference.toLowerCase().includes(q) ||
        d.assure.toLowerCase().includes(q) ||
        d.telephone.toLowerCase().includes(q);
      return matchesFilter && matchesSearch;
    });
  }, [dossiers, activeFilter, search]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {filters.map((f) => (
            <button
              key={f.key}
              onClick={() => setActiveFilter(f.key)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                activeFilter === f.key
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/70"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <label className="sr-only" htmlFor="dossier-search">
          Rechercher un dossier
        </label>
        <input
          id="dossier-search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Rechercher par r\u00e9f\u00e9rence, nom ou t\u00e9l\u00e9phone"
          className="w-72 rounded-lg border border-border bg-card px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary/30"
        />
      </div>

      <div className="overflow-hidden rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
            <tr>
              <th className="px-4 py-2 font-medium">{"R\u00e9f\u00e9rence"}</th>
              <th className="px-4 py-2 font-medium">{"Assur\u00e9"}</th>
              <th className="px-4 py-2 font-medium">{"Type"}</th>
              <th className="px-4 py-2 font-medium">{"Date"}</th>
              <th className="px-4 py-2 font-medium">{"Agent"}</th>
              <th className="px-4 py-2 font-medium">{"Statut"}</th>
              <th className="px-4 py-2 font-medium">{"Confiance IA"}</th>
              <th className="px-4 py-2 font-medium">{"Actions"}</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((d) => (
              <tr key={d.reference} className="border-t border-border">
                <td className="px-4 py-2 font-medium">{d.reference}</td>
                <td className="px-4 py-2">{d.assure}</td>
                <td className="px-4 py-2">{d.type}</td>
                <td className="px-4 py-2">{d.date}</td>
                <td className="px-4 py-2">{d.agent}</td>
                <td className="px-4 py-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusStyles[d.statut]}`}
                  >
                    {d.statut}
                  </span>
                </td>
                <td className="px-4 py-2">{d.confiance}%</td>
                <td className="px-4 py-2">
                  <button
                    onClick={() => onSelect(d.reference)}
                    className="text-xs font-medium text-primary underline underline-offset-2"
                  >
                    {"Ouvrir"}
                  </button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-6 text-center text-muted-foreground">
                  {"Aucun dossier ne correspond \u00e0 ces crit\u00e8res."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
