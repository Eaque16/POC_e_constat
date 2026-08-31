interface KpiCardProps {
  label: string;
  value: string | number;
  accent?: "default" | "warning" | "success";
}

const accentStyles: Record<NonNullable<KpiCardProps["accent"]>, string> = {
  default: "text-foreground",
  warning: "text-warning",
  success: "text-success",
};

export function KpiCard({ label, value, accent = "default" }: KpiCardProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${accentStyles[accent]}`}>{value}</p>
    </div>
  );
}
