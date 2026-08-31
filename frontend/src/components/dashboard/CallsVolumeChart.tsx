import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import type { CallVolumePoint } from "../../types/dashboard";

interface CallsVolumeChartProps {
  data: CallVolumePoint[];
}

export default function CallsVolumeChart({ data }: CallsVolumeChartProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
      <h3 className="text-sm font-semibold text-blue-950 mb-3">
        Volume d'appels par heure
      </h3>
      <ResponsiveContainer width="100%" height={260}>
        <AreaChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="colorAppels" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#2563eb" stopOpacity={0.35} />
              <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="hour" tick={{ fontSize: 12, fill: "#6b7280" }} />
          <YAxis tick={{ fontSize: 12, fill: "#6b7280" }} allowDecimals={false} />
          <Tooltip
            contentStyle={{ borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 13 }}
          />
          <Area
            type="monotone"
            dataKey="appels"
            stroke="#2563eb"
            strokeWidth={2}
            fill="url(#colorAppels)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}