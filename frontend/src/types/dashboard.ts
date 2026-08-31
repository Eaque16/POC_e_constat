export interface KpiData {
  label: string;
  value: string | number;
  change?: number; // pourcentage d'evolution, ex: 4.2 ou -2.1
  trend?: "up" | "down" | "flat";
}

export interface CallVolumePoint {
  hour: string;
  appels: number;
}

export interface ClassificationSlice {
  categorie: string;
  valeur: number;
  couleur: string;
}