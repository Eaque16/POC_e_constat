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

interface DossiersByTypeChartProps {
  dossiers: Dossier[];
}

const CHART_COLOR = "#3b6bd6";

export function DossiersByTypeChart({ dossiers }: DossiersByTypeChartProps) {
  const counts = new Map<string, number>();
  dossiers.forEach((d) => {
    counts.set(d.type, (counts.get(d.type) ?? 0) + 1);
  });
  const data = Array.from(counts.entries()).map(([type, count]) => ({
    type,
    count,
  }));

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <h3 className="text-sm font-semibold text-muted-foreground">
        {"Dossiers par type"}
      </h3>
      <div className="mt-3 h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" allowDecimals={false} fontSize={11} />
            <YAxis dataKey="type" type="category" width={140} fontSize={10} />
            <Tooltip />
            <Bar dataKey="count" fill={CHART_COLOR} radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
