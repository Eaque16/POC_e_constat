import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { ArrowRight, Bot, Database, FolderCheck, PhoneCall, Sparkles } from "lucide-react";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { getDashboard, listSinistres } from "@/services/sinistres";
import type { DashboardStats } from "@/services/sinistres";
import type { SinistreResponse } from "@/types/api";

export function DashboardReal() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [claims, setClaims] = useState<SinistreResponse[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getDashboard(), listSinistres()])
      .then(([dashboard, dossiers]) => {
        setStats(dashboard);
        setClaims(dossiers);
      })
      .catch(() => setError("Impossible de charger les données réelles du backend."));
  }, []);

  if (error) return <p className="rounded-xl bg-destructive/10 p-4 text-destructive">{error}</p>;
  if (!stats) return <p className="text-sm text-muted-foreground">Chargement du tableau de bord…</p>;

  return (
    <div className="space-y-7">
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-950 via-blue-950 to-primary p-7 text-white shadow-xl shadow-blue-950/10 lg:p-9">
        <div className="absolute -right-20 -top-24 h-72 w-72 rounded-full bg-blue-400/15 blur-3xl" />
        <div className="relative max-w-3xl"><div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-blue-200"><Sparkles className="h-4 w-4" /> Centre de pilotage intelligent</div><h1 className="text-3xl font-bold tracking-tight lg:text-4xl">Bonjour, votre activité en un coup d’œil.</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-blue-100/75">Gérez les déclarations, assistez les appels et suivez les validations depuis un espace de travail unifié.</p><div className="mt-6 flex flex-wrap gap-3"><Link to="/appels" className="inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-slate-950 shadow-lg transition hover:-translate-y-0.5"><PhoneCall className="h-4 w-4" /> Ouvrir le poste d’appel</Link><Link to="/dossiers" className="inline-flex items-center gap-2 rounded-xl border border-white/20 bg-white/10 px-4 py-2.5 text-sm font-semibold text-white backdrop-blur transition hover:bg-white/15">Voir les dossiers <ArrowRight className="h-4 w-4" /></Link></div></div>
      </section>

      <div><h2 className="text-lg font-bold text-slate-950">Indicateurs opérationnels</h2><p className="text-sm text-muted-foreground">Les chiffres essentiels pour traiter les priorités.</p></div>
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <KpiCard label="Appels" value={stats.appels} />
        <KpiCard label="Dossiers" value={stats.dossiers} />
        <KpiCard label="À valider" value={stats.dossiers_a_valider} accent="warning" />
        <KpiCard label="Validés" value={stats.dossiers_valides} accent="success" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Link to="/assistant-ia" className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:border-blue-200 hover:shadow-lg"><div className="mb-4 grid h-11 w-11 place-items-center rounded-xl bg-blue-50 text-blue-700"><Bot className="h-5 w-5" /></div><h3 className="font-bold">Assistant IA</h3><p className="mt-1 text-sm leading-5 text-muted-foreground">Analyser un échange et compléter un constat.</p><span className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-primary">Accéder <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1" /></span></Link>
        <Link to="/dossiers" className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:border-emerald-200 hover:shadow-lg"><div className="mb-4 grid h-11 w-11 place-items-center rounded-xl bg-emerald-50 text-emerald-700"><FolderCheck className="h-5 w-5" /></div><h3 className="font-bold">File de validation</h3><p className="mt-1 text-sm leading-5 text-muted-foreground">Contrôler et valider les dossiers en attente.</p><span className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-primary">Traiter les dossiers <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1" /></span></Link>
        <Link to="/donnees" className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:border-violet-200 hover:shadow-lg"><div className="mb-4 grid h-11 w-11 place-items-center rounded-xl bg-violet-50 text-violet-700"><Database className="h-5 w-5" /></div><h3 className="font-bold">Interroger les données</h3><p className="mt-1 text-sm leading-5 text-muted-foreground">Rechercher, filtrer et consulter les données métier.</p><span className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-primary">Ouvrir l’explorateur <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1" /></span></Link>
      </div>

      <section className="flex flex-col justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:flex-row sm:items-center"><div><h2 className="font-bold">Activité récente</h2><p className="mt-1 text-sm text-muted-foreground">{claims.length} dossiers disponibles · {stats.dossiers_en_cours} traitements en cours · {stats.erreurs_traitement} erreur(s)</p></div><Link to="/donnees" className="inline-flex items-center gap-2 text-sm font-semibold text-primary">Consulter les données <ArrowRight className="h-4 w-4" /></Link></section>
    </div>
  );
}
