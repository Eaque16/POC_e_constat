import type { Agent, AgentStatus } from "@/data/mockAgents";

interface AgentListProps {
  agents: Agent[];
}

const statusStyles: Record<AgentStatus, string> = {
  Disponible: "bg-success/15 text-success",
  "En appel": "bg-primary/10 text-primary",
  Pause: "bg-warning/15 text-warning",
  "Hors ligne": "bg-muted text-muted-foreground",
};

export function AgentList({ agents }: AgentListProps) {
  return (
    <div className="overflow-hidden rounded-xl border border-border">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
          <tr>
            <th className="px-4 py-2 font-medium">{"Nom"}</th>
            <th className="px-4 py-2 font-medium">{"R\u00f4le"}</th>
            <th className="px-4 py-2 font-medium">{"Statut"}</th>
            <th className="px-4 py-2 font-medium">{"Appels aujourd'hui"}</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((agent) => (
            <tr key={agent.id} className="border-t border-border">
              <td className="px-4 py-2 font-medium">{agent.name}</td>
              <td className="px-4 py-2 text-muted-foreground">{agent.role}</td>
              <td className="px-4 py-2">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusStyles[agent.status]}`}
                >
                  {agent.status}
                </span>
              </td>
              <td className="px-4 py-2">{agent.callsToday}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
