import { useMemo, useState } from "react";
import type { SinistreResponse } from "@/types/api";

interface SinistreListProps {
  sinistres: SinistreResponse[];
  onSelect: (id: string) => void;
}

const statusStyles: Record<string, string> = {
  nouveau: "bg-primary/10 text-primary",
  en_cours: "bg-primary/10 text-primary",
  en_attente_validation: "bg-warning/15 text-warning",
  valide: "bg-success/15 text-success",
  rejete: "bg-destructive/10 text-destructive",
  transmis_econsta: "bg-success/15 text-success",
};

function getAssureNom(s: SinistreResponse): string {
  const data = s.donnees_structurees as { assure_nom?: string } | null;
  return data?.assure_nom ?? "-";
}

function getType(s: SinistreResponse): string {
  const data = s.donnees_structurees as { type_accident?: string } | null;
  return data?.type_accident ?? "-";
}

export function SinistreList({ sinistres, onSelect }: SinistreListProps) {
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return sinistres;
    return sinistres.filter((s) => {
      const nom = getAssureNom(s).toLowerCase();
      return (
        (s.reference ?? "").toLowerCase().includes(q) ||
        nom.includes(q)
      );
    });
  }, [sinistres, search]);

  return (
    <div className="space-y-4">
      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Rechercher par r\u00e9f\u00e9rence ou nom"
        className="w-72 rounded-lg border border-border bg-card px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-primary/30"
      />

      <div className="overflow-hidden rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
            <tr>
              <th className="px-4 py-2 font-medium">{"R\u00e9f\u00e9rence"}</th>
              <th className="px-4 py-2 font-medium">{"Assur\u00e9"}</th>
              <th className="px-4 py-2 font-medium">{"Type"}</th>
              <th className="px-4 py-2 font-medium">{"Statut"}</th>
              <th className="px-4 py-2 font-medium">{"Confiance IA"}</th>
              <th className="px-4 py-2 font-medium">{"Actions"}</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((s) => (
              <tr key={s.id} className="border-t border-border">
                <td className="px-4 py-2 font-medium">{s.reference ?? s.id.slice(0, 8)}</td>
                <td className="px-4 py-2">{getAssureNom(s)}</td>
                <td className="px-4 py-2">{getType(s)}</td>
                <td className="px-4 py-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusStyles[s.statut] ?? "bg-muted text-muted-foreground"}`}
                  >
                    {s.statut}
                  </span>
                </td>
                <td className="px-4 py-2">{Math.round(s.niveau_confiance * 100)}%</td>
                <td className="px-4 py-2">
                  <button
                    onClick={() => onSelect(s.id)}
                    className="text-xs font-medium text-primary underline underline-offset-2"
                  >
                    {"Ouvrir"}
                  </button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                  {"Aucun dossier."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
