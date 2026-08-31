export interface VehicleInfo {
  marque: string | null;
  modele: string | null;
  immatriculation: string | null;
  annee: string | null;
  type_vehicule: string | null;
  couleur: string | null;
}

export interface PersonInfo {
  nom_complet: string | null;
  telephone: string | null;
  email: string | null;
  adresse: string | null;
}

export interface SinistreData {
  assure_nom: string | null;
  assure_telephone: string | null;
  assure_email: string | null;
  assure_adresse: string | null;
  date_sinistre: string | null;
  heure_sinistre: string | null;
  lieu_sinistre: string | null;
  type_accident: string | null;
  description: string | null;
  vehicule_assure: VehicleInfo | null;
  vehicule_tiers: VehicleInfo | null;
  dommages_assure: string | null;
  dommages_tiers: string | null;
  immobilisation: boolean | null;
  besoin_assistance: boolean | null;
  tiers_nom: string | null;
  tiers_telephone: string | null;
  tiers_assurance: string | null;
  temoins: PersonInfo[];
  resume_automatique: string | null;
  niveau_confiance: number;
}

export interface SinistreResponse {
  id: string;
  reference: string | null;
  statut: string;
  donnees_structurees: SinistreData | Record<string, unknown> | null;
  infos_manquantes: Record<string, unknown>[];
  niveau_confiance: number;
  resume: string | null;
  agent_id: string | null;
  notes_agent: string | null;
  valide_par: string | null;
  valide_le: string | null;
  transmis_econsta_le: string | null;
  econsta_reference: string | null;
  created_at: string;
  updated_at: string;
}

export interface AnalysisResponse {
  sinistre_id: string;
  reference: string | null;
  donnees_structurees: Record<string, unknown>;
  infos_manquantes: Record<string, unknown>[];
  niveau_confiance: number;
  resume: string | null;
  statut: string;
}

export interface StatsResponse {
  total: number;
  nouveau: number;
  en_cours: number;
  en_attente_validation: number;
  valide: number;
  rejete: number;
  transmis_econsta: number;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  agent_id: string | null;
  nom_utilisateur: string | null;
  role: string | null;
}

export interface SinistreListResponse {
  items?: SinistreResponse[];
  sinistres?: SinistreResponse[];
  total?: number;
}
