import type { Agent } from "../../types/agent";
import AgentStatusBadge from "./AgentStatusBadge";

interface AgentsTableProps {
  agents: Agent[];
}

export default function AgentsTable({ agents }: AgentsTableProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-gray-500 text-left">
          <tr>
            <th className="px-4 py-3 font-medium">Agent</th>
            <th className="px-4 py-3 font-medium">Statut</th>
            <th className="px-4 py-3 font-medium">Appels aujourd'hui</th>
            <th className="px-4 py-3 font-medium">Temps moyen</th>
            <th className="px-4 py-3 font-medium">Validation IA</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {agents.map((agent) => (
            <tr key={agent.id} className="hover:bg-gray-50">
              <td className="px-4 py-3">
                <div className="font-medium text-blue-950">{agent.nom}</div>
                <div className="text-xs text-gray-400">{agent.email}</div>
              </td>
              <td className="px-4 py-3">
                <AgentStatusBadge statut={agent.statut} />
              </td>
              <td className="px-4 py-3">{agent.appelsAujourdhui}</td>
              <td className="px-4 py-3">{agent.tempsMoyenAppel}</td>
              <td className="px-4 py-3">
                {agent.tauxValidationIA > 0 ? `${agent.tauxValidationIA}%` : "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}