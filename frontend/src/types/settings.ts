export interface AppSettings {
  langueInterface: "fr" | "en";
  notificationsActives: boolean;
  transcriptionAutomatique: boolean;
  suggestionsCopilotActives: boolean;
  seuilConfianceIA: number; // 0-100
}