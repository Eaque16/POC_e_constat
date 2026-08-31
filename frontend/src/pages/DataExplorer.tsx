import { useEffect, useMemo, useState } from "react";
import { Database, Filter, RefreshCw, Search, SlidersHorizontal } from "lucide-react";
import { listSinistres } from "@/services/sinistres";
import type { SinistreResponse } from "@/types/api";

export function DataExplorerPage() {
  const [claims, setClaims] = useState<SinistreResponse[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("tous");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true); setError(null);
    listSinistres().then(setClaims).catch(() => setError("Impossible de charger les données.")).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const statuses = useMemo(() => [...new Set(claims.map((claim) => claim.statut))], [claims]);
  const filtered = useMemo(() => claims.filter((claim) => {
    const data = claim.donnees_structurees as Record<string, unknown> | null;
    const searchable = [claim.reference, claim.statut, data?.nom_assure, data?.assure_nom, data?.lieu, data?.type_accident].join(" ").toLowerCase();
    return (status === "tous" || claim.statut === status) && searchable.includes(query.trim().toLowerCase());
  }), [claims, query, status]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div><div className="mb-2 flex items-center gap-2 text-sm font-semibold text-primary"><Database className="h-4 w-4" /> Données & analyses</div><h1 className="text-3xl font-bold tracking-tight text-slate-950">Explorateur de données</h1><p className="mt-1 text-sm text-muted-foreground">Interrogez les dossiers et les données extraites sans encombrer le parcours opérationnel.</p></div>
        <button onClick={load} className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold shadow-sm transition hover:bg-slate-50"><RefreshCw className="h-4 w-4" /> Actualiser</button>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-3 lg:flex-row">
          <div className="relative flex-1"><Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Référence, assuré, lieu ou type d’accident…" className="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 pl-10 pr-4 text-sm outline-none focus:border-primary/40 focus:bg-white focus:ring-4 focus:ring-primary/5" /></div>
          <div className="relative min-w-56"><Filter className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><select value={status} onChange={(event) => setStatus(event.target.value)} className="h-11 w-full appearance-none rounded-xl border border-slate-200 bg-white pl-10 pr-8 text-sm outline-none focus:border-primary/40"><option value="tous">Tous les statuts</option>{statuses.map((item) => <option key={item}>{item}</option>)}</select></div>
        </div>
        <div className="mt-4 flex items-center gap-2 border-t border-slate-100 pt-4 text-xs text-muted-foreground"><SlidersHorizontal className="h-3.5 w-3.5" /><strong className="text-foreground">{filtered.length}</strong> résultat{filtered.length > 1 ? "s" : ""} sur {claims.length} dossiers</div>
      </section>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        {loading ? <p className="p-8 text-center text-sm text-muted-foreground">Chargement des données…</p> : error ? <p className="p-8 text-center text-sm text-destructive">{error}</p> : (
          <div className="overflow-x-auto"><table className="w-full text-sm"><thead className="bg-slate-50 text-left text-[11px] uppercase tracking-wider text-slate-500"><tr><th className="px-5 py-3.5">Référence</th><th className="px-5 py-3.5">Assuré</th><th className="px-5 py-3.5">Lieu</th><th className="px-5 py-3.5">Type</th><th className="px-5 py-3.5">Statut</th><th className="px-5 py-3.5 text-right">Confiance</th></tr></thead><tbody className="divide-y divide-slate-100">{filtered.map((claim) => { const data = claim.donnees_structurees as Record<string, unknown> | null; return <tr key={claim.id} className="transition hover:bg-slate-50/80"><td className="px-5 py-4 font-semibold text-primary">{claim.reference}</td><td className="px-5 py-4">{String(data?.nom_assure ?? data?.assure_nom ?? "—")}</td><td className="px-5 py-4 text-muted-foreground">{String(data?.lieu ?? "—")}</td><td className="px-5 py-4 text-muted-foreground">{String(data?.type_accident ?? "—")}</td><td className="px-5 py-4"><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium">{claim.statut}</span></td><td className="px-5 py-4 text-right font-semibold">{Math.round(claim.niveau_confiance * 100)}%</td></tr>; })}</tbody></table>{filtered.length === 0 && <p className="p-10 text-center text-sm text-muted-foreground">Aucun dossier ne correspond à ces critères.</p>}</div>
        )}
      </section>
    </div>
  );
}
