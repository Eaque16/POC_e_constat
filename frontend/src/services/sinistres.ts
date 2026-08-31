import { api } from "@/services/api";
import type { AnalysisResponse, SinistreResponse, StatsResponse } from "@/types/api";

interface BackendClaim {
  id: string;
  status: string;
  current_data: Record<string, unknown>;
  missing_fields: string[];
  global_confidence: number;
  validated_by: string | null;
  validated_at: string | null;
  external_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface DashboardStats {
  appels: number;
  dossiers: number;
  dossiers_en_cours: number;
  dossiers_a_valider: number;
  dossiers_valides: number;
  dossiers_envoyes: number;
  erreurs_traitement: number;
  temps_moyen_traitement_secondes: number | null;
  taux_dossiers_corriges_pct: number;
  taux_dossiers_sans_correction_pct: number;
  distribution_types_accident: Record<string, number>;
  distribution_erreurs: Record<string, number>;
  alertes: string[];
}

const STATUS_LABELS: Record<string, string> = {
  pending_validation: "en_attente_validation",
  validated: "valide",
  sent: "transmis_econsta",
  processing: "en_cours",
};

function toSinistre(claim: BackendClaim): SinistreResponse {
  const data = claim.current_data ?? {};
  return {
    id: claim.id,
    reference: `SIN-${claim.id.slice(0, 8).toUpperCase()}`,
    statut: STATUS_LABELS[claim.status] ?? claim.status,
    donnees_structurees: data,
    infos_manquantes: (claim.missing_fields ?? []).map((champ) => ({ champ })),
    niveau_confiance: claim.global_confidence,
    resume: typeof data.circonstances === "string" ? data.circonstances : null,
    agent_id: null,
    notes_agent: null,
    valide_par: claim.validated_by,
    valide_le: claim.validated_at,
    transmis_econsta_le: claim.status === "sent" ? claim.updated_at : null,
    econsta_reference: claim.external_id,
    created_at: claim.created_at,
    updated_at: claim.updated_at,
  };
}

export async function listSinistres(): Promise<SinistreResponse[]> {
  return (await api.get<BackendClaim[]>("/claims")).map(toSinistre);
}

export async function getSinistre(id: string): Promise<SinistreResponse> {
  return toSinistre(await api.get<BackendClaim>(`/claims/${id}`));
}

export async function getDashboard(): Promise<DashboardStats> {
  return api.get<DashboardStats>("/dashboard");
}

export async function getStats(): Promise<StatsResponse> {
  const stats = await getDashboard();
  return {
    total: stats.dossiers,
    nouveau: 0,
    en_cours: stats.dossiers_en_cours,
    en_attente_validation: stats.dossiers_a_valider,
    valide: stats.dossiers_valides,
    rejete: 0,
    transmis_econsta: stats.dossiers_envoyes,
  };
}

export async function validateSinistre(
  id: string,
  _agentId?: string,
): Promise<SinistreResponse> {
  await api.post(`/claims/${id}/validate`, {});
  return getSinistre(id);
}

export async function rejectSinistre(
  _id?: string,
  _agentId?: string,
  _raison?: string,
): Promise<never> {
  throw new Error("Le rejet n'est pas encore exposé par l'API E-Constat.");
}

export async function transmitToEconsta(id: string): Promise<SinistreResponse> {
  await api.post(`/claims/${id}/send`, {});
  return getSinistre(id);
}

export async function getHistorique(id: string): Promise<unknown> {
  return api.get(`/claims/${id}`);
}

export async function analyzeTranscription(_transcription: string): Promise<AnalysisResponse> {
  throw new Error("L'analyse directe de texte n'est pas exposée par le backend actuel.");
}

export async function uploadAudioAndAnalyze(
  audioBlob: Blob,
  _language = "fr",
): Promise<AnalysisResponse> {
  const form = new FormData();
  form.append("audio", audioBlob, "appel.webm");
  form.append("profile", "quality");
  const job = await api.post<{ id: string; job_id: string }>("/calls", form);
  return {
    sinistre_id: job.id,
    reference: job.job_id,
    donnees_structurees: {},
    infos_manquantes: [],
    niveau_confiance: 0,
    resume: "Audio accepté. Le traitement est exécuté par le worker.",
    statut: "en_cours",
  };
}
