import type { AgentStatus } from "../../types/agent";

interface AgentStatusBadgeProps {
  statut: AgentStatus;
}

const statusConfig: Record<AgentStatus, { label: string; classes: string }> = {
  disponible: { label: "Disponible", classes: "bg-green-100 text-green-700" },
  en_appel: { label: "En appel", classes: "bg-blue-100 text-blue-700" },
  pause: { label: "En pause", classes: "bg-amber-100 text-amber-700" },
  hors_ligne: { label: "Hors ligne", classes: "bg-gray-100 text-gray-500" },
};

export default function AgentStatusBadge({ statut }: AgentStatusBadgeProps) {
  const config = statusConfig[statut];
  return (
    <span className={`text-xs font-medium px-2 py-1 rounded-full ${config.classes}`}>
      {config.label}
    </span>
  );
}