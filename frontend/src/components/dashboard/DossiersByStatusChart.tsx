import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { Dossier } from "@/data/mockDossiers";

interface DossiersByStatusChartProps {
  dossiers: Dossier[];
}

const CHART_COLOR = "#1e3a6e";

export function DossiersByStatusChart({ dossiers }: DossiersByStatusChartProps) {
  const counts = new Map<string, number>();
  dossiers.forEach((d) => {
    counts.set(d.statut, (counts.get(d.statut) ?? 0) + 1);
  });
  const data = Array.from(counts.entries()).map(([statut, count]) => ({
    statut,
    count,
  }));

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <h3 className="text-sm font-semibold text-muted-foreground">
        {"Dossiers par statut"}
      </h3>
      <div className="mt-3 h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="statut" fontSize={11} />
            <YAxis allowDecimals={false} fontSize={11} />
            <Tooltip />
            <Bar dataKey="count" fill={CHART_COLOR} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
