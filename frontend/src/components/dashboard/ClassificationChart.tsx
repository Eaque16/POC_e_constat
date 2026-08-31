import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
} from "recharts";
import type { ClassificationSlice } from "../../types/dashboard";

interface ClassificationChartProps {
  data: ClassificationSlice[];
}

export default function ClassificationChart({ data }: ClassificationChartProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
      <h3 className="text-sm font-semibold text-blue-950 mb-3">
        Repartition des classifications IA
      </h3>
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Pie
            data={data}
            dataKey="valeur"
            nameKey="categorie"
            innerRadius={55}
            outerRadius={90}
            paddingAngle={2}
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.couleur} />
            ))}
          </Pie>
          <Tooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}