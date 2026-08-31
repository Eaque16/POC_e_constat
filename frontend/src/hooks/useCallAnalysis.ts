import { useMemo } from "react";
import type { TranscriptTurn } from "@/types/transcription";

export interface Suggestion {
  id: string;
  text: string;
}

export type BadgeKind = "detected" | "missing" | "question" | "urgent";

export interface AnalysisBadge {
  id: string;
  kind: BadgeKind;
  label: string;
}

export type FieldStatus = "confirme" | "a_verifier" | "manquant";

export interface ExtractedField {
  key: string;
  label: string;
  value: string | null;
  status: FieldStatus;
}

export const CLASSIFICATION_CATEGORIES = [
  "Accident automobile",
  "D\u00e9claration de sinistre",
  "Assistance automobile",
  "Assurance sant\u00e9",
  "Paiement",
  "Contrat",
  "R\u00e9clamation",
  "Urgence",
  "Autre",
] as const;

export type ClassificationCategory = (typeof CLASSIFICATION_CATEGORIES)[number];

export interface ClassificationResult {
  category: ClassificationCategory | "En cours d'analyse";
  confidence: number;
}

const CATEGORY_KEYWORDS: Record<ClassificationCategory, string[]> = {
  "Accident automobile": ["accident", "accrochage", "collision"],
  "D\u00e9claration de sinistre": ["declarer", "d\u00e9clarer", "sinistre"],
  "Assistance automobile": ["panne", "remorquage", "d\u00e9panneuse", "depanneuse"],
  "Assurance sant\u00e9": ["consultation", "medecin", "m\u00e9decin", "hopital", "h\u00f4pital"],
  Paiement: ["paiement", "remboursement", "facture"],
  Contrat: ["contrat", "souscription", "renouvellement"],
  "R\u00e9clamation": ["reclamation", "r\u00e9clamation", "plainte", "delai", "d\u00e9lai"],
  Urgence: ["urgence", "urgent", "grave"],
  Autre: [],
};

const URGENT_KEYWORDS = ["blesse", "bless\u00e9", "urgence", "grave"];
const VEHICLE_KEYWORDS = ["voiture", "v\u00e9hicule", "accrochage", "accident"];

function analyzeTurns(turns: TranscriptTurn[]) {
  const fullText = turns.map((t) => t.text.toLowerCase()).join(" ");

  const badges: AnalysisBadge[] = [];

  if (VEHICLE_KEYWORDS.some((kw) => fullText.includes(kw))) {
    badges.push({
      id: "detected-accident",
      kind: "detected",
      label: "Accident automobile",
    });
  }

  if (URGENT_KEYWORDS.some((kw) => fullText.includes(kw))) {
    badges.push({
      id: "urgent-injury",
      kind: "urgent",
      label: "Blessure potentielle mentionn\u00e9e",
    });
  }

  if (fullText.includes("immatriculation") === false && turns.length > 0) {
    badges.push({
      id: "missing-plate",
      kind: "missing",
      label: "Num\u00e9ro d'immatriculation",
    });
  }

  if (turns.length > 0 && turns.length < 4) {
    badges.push({
      id: "question-location",
      kind: "question",
      label: "Demander le lieu exact de l'accident",
    });
  }

  return badges;
}

function buildSuggestion(turns: TranscriptTurn[]): Suggestion | null {
  if (turns.length === 0) return null;

  const fullText = turns.map((t) => t.text.toLowerCase()).join(" ");

  if (!fullText.includes("immatriculation")) {
    return {
      id: "sugg-plate",
      text: "Pouvez-vous me pr\u00e9ciser le num\u00e9ro d'immatriculation du v\u00e9hicule ?",
    };
  }

  if (URGENT_KEYWORDS.some((kw) => fullText.includes(kw))) {
    return {
      id: "sugg-injury",
      text: "Y a-t-il des personnes bless\u00e9es n\u00e9cessitant une assistance imm\u00e9diate ?",
    };
  }

  return {
    id: "sugg-generic",
    text: "Pouvez-vous me donner plus de d\u00e9tails sur les circonstances de l'accident ?",
  };
}

function buildClassification(turns: TranscriptTurn[]): ClassificationResult {
  if (turns.length === 0) {
    return { category: "En cours d'analyse", confidence: 0 };
  }

  const fullText = turns.map((t) => t.text.toLowerCase()).join(" ");

  for (const category of CLASSIFICATION_CATEGORIES) {
    const keywords = CATEGORY_KEYWORDS[category];
    if (keywords.length > 0 && keywords.some((kw) => fullText.includes(kw))) {
      return {
        category,
        confidence: Math.min(96, 55 + turns.length * 8),
      };
    }
  }

  return { category: "Autre", confidence: 35 };
}

function buildExtractedFields(
  turns: TranscriptTurn[],
  callerName: string,
  callerPhone: string,
  contractNumber: string | null
): ExtractedField[] {
  const fullText = turns.map((t) => t.text.toLowerCase()).join(" ");
  const now = new Date();

  const has = (kw: string) => fullText.includes(kw);
  const someHas = (kws: string[]) => kws.some((kw) => fullText.includes(kw));

  return [
    { key: "nom", label: "Nom assur\u00e9", value: callerName, status: "confirme" },
    { key: "telephone", label: "T\u00e9l\u00e9phone", value: callerPhone, status: "confirme" },
    {
      key: "contrat",
      label: "Num\u00e9ro contrat",
      value: contractNumber,
      status: contractNumber ? "confirme" : "manquant",
    },
    {
      key: "date",
      label: "Date",
      value: turns.length > 0 ? now.toLocaleDateString("fr-FR") : null,
      status: turns.length > 0 ? "confirme" : "manquant",
    },
    {
      key: "heure",
      label: "Heure",
      value: turns.length > 0 ? now.toLocaleTimeString("fr-FR").slice(0, 5) : null,
      status: turns.length > 0 ? "confirme" : "manquant",
    },
    {
      key: "lieu",
      label: "Lieu",
      value: has("cocody") ? "Cocody, Abidjan" : null,
      status: has("cocody") ? "a_verifier" : "manquant",
    },
    {
      key: "type_sinistre",
      label: "Type de sinistre",
      value: someHas(VEHICLE_KEYWORDS) ? "Accident automobile" : null,
      status: someHas(VEHICLE_KEYWORDS) ? "a_verifier" : "manquant",
    },
    {
      key: "vehicule",
      label: "V\u00e9hicule",
      value: someHas(["voiture", "v\u00e9hicule"]) ? "V\u00e9hicule impliqu\u00e9 mentionn\u00e9" : null,
      status: someHas(["voiture", "v\u00e9hicule"]) ? "a_verifier" : "manquant",
    },
    { key: "immatriculation", label: "Immatriculation", value: null, status: "manquant" },
    {
      key: "circonstances",
      label: "Circonstances",
      value: turns.length > 1 ? "D\u00e9crites partiellement par l'assur\u00e9" : null,
      status: turns.length > 1 ? "a_verifier" : "manquant",
    },
    {
      key: "dommages",
      label: "Dommages",
      value: has("degat") || has("d\u00e9g\u00e2t") || has("abime") || has("abim\u00e9")
        ? "D\u00e9g\u00e2ts mentionn\u00e9s"
        : null,
      status: has("degat") || has("d\u00e9g\u00e2t") ? "a_verifier" : "manquant",
    },
    {
      key: "blesses",
      label: "Bless\u00e9s",
      value: someHas(URGENT_KEYWORDS) ? "Possible" : "Non signal\u00e9",
      status: someHas(URGENT_KEYWORDS) ? "a_verifier" : "manquant",
    },
    { key: "temoins", label: "T\u00e9moins", value: null, status: "manquant" },
  ];
}

export function useCallAnalysis(
  turns: TranscriptTurn[],
  callerName: string,
  callerPhone: string,
  contractNumber: string | null = null
) {
  const badges = useMemo(() => analyzeTurns(turns), [turns]);
  const suggestion = useMemo(() => buildSuggestion(turns), [turns]);
  const classification = useMemo(() => buildClassification(turns), [turns]);
  const extractedFields = useMemo(
    () => buildExtractedFields(turns, callerName, callerPhone, contractNumber),
    [turns, callerName, callerPhone, contractNumber]
  );

  return { badges, suggestion, classification, extractedFields };
}
