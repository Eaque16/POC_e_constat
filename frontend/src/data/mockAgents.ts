export type AgentStatus = "Disponible" | "En appel" | "Pause" | "Hors ligne";

export interface Agent {
  id: string;
  name: string;
  role: string;
  status: AgentStatus;
  callsToday: number;
}

export const mockAgents: Agent[] = [
  { id: "a1", name: "Awa Traor\u00e9", role: "Agent senior", status: "En appel", callsToday: 12 },
  { id: "a2", name: "Serge Bamba", role: "Agent", status: "Disponible", callsToday: 9 },
  { id: "a3", name: "Fatou Coulibaly", role: "Agent", status: "Pause", callsToday: 7 },
  { id: "a4", name: "Yao Kouam\u00e9", role: "Superviseur", status: "Disponible", callsToday: 4 },
  { id: "a5", name: "Rachel Amoin", role: "Agent", status: "Hors ligne", callsToday: 0 },
];
