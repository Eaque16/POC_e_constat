export type AgentStatus = "disponible" | "en_appel" | "pause" | "hors_ligne";

export interface Agent {
  id: string;
  nom: string;
  email: string;
  statut: AgentStatus;
  appelsAujourdhui: number;
  tempsMoyenAppel: string;
  tauxValidationIA: number; // pourcentage
}