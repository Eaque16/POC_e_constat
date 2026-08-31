export interface MockCaller {
  name: string;
  phone: string;
  contractNumber: string | null;
}

export const mockCaller: MockCaller = {
  name: "Jean Kouassi",
  phone: "+225 07 07 12 34 56",
  contractNumber: "CT-2024-88213",
};

export interface MockClaimFolder {
  reference: string;
  type: string;
  status: "\u00c0 v\u00e9rifier" | "Valid\u00e9" | "Nouveau";
  confidence: number;
  missingFields: string[];
}

export const mockClaimFolder: MockClaimFolder = {
  reference: "SIN-2026-00124",
  type: "Accident automobile",
  status: "\u00c0 v\u00e9rifier",
  confidence: 74,
  missingFields: [
    "Num\u00e9ro d'immatriculation",
    "Nombre de v\u00e9hicules impliqu\u00e9s",
    "Pr\u00e9sence de bless\u00e9s",
  ],
};
