export type DossierStatus =
  | "Nouveau"
  | "En cours"
  | "A verifier"
  | "Valide"
  | "Transmis"
  | "Cloture";

export interface DossierTranscriptLine {
  speaker: "agent" | "assure";
  text: string;
}

export interface DossierField {
  label: string;
  value: string | null;
  status: "confirme" | "a_verifier" | "manquant";
}

export interface Dossier {
  reference: string;
  assure: string;
  telephone: string;
  type: string;
  date: string;
  agent: string;
  statut: DossierStatus;
  confiance: number;
  lieu: string;
  resume: string;
  transcription: DossierTranscriptLine[];
  extractedFields: DossierField[];
}

export const mockDossiers: Dossier[] = [
  {
    reference: "SIN-2026-00124",
    assure: "Jean Kouassi",
    telephone: "+225 07 07 12 34 56",
    type: "Accident automobile",
    date: "2026-08-20",
    agent: "Awa Traor\u00e9",
    statut: "A verifier",
    confiance: 74,
    lieu: "Cocody, Abidjan",
    resume:
      "Accrochage entre deux vehicules au feu rouge, pas de blesses signales.",
    transcription: [
      { speaker: "assure", text: "Bonjour, j'ai eu un accident ce matin a Cocody." },
      { speaker: "agent", text: "Bonjour, je vais vous aider a declarer votre sinistre." },
      { speaker: "assure", text: "C'est un accrochage avec une autre voiture au feu rouge." },
      { speaker: "agent", text: "Y a-t-il des blesses ou des degats importants ?" },
      { speaker: "assure", text: "Non, pas de blesses, juste le pare-choc abime." },
    ],
    extractedFields: [
      { label: "Nom assur\u00e9", value: "Jean Kouassi", status: "confirme" },
      { label: "T\u00e9l\u00e9phone", value: "+225 07 07 12 34 56", status: "confirme" },
      { label: "Num\u00e9ro contrat", value: "CT-2024-88213", status: "confirme" },
      { label: "Date", value: "2026-08-20", status: "confirme" },
      { label: "Heure", value: "08:14", status: "confirme" },
      { label: "Lieu", value: "Cocody, Abidjan", status: "confirme" },
      { label: "Type de sinistre", value: "Accident automobile", status: "confirme" },
      { label: "V\u00e9hicule", value: "V\u00e9hicule impliqu\u00e9 mentionn\u00e9", status: "a_verifier" },
      { label: "Immatriculation", value: null, status: "manquant" },
      { label: "Circonstances", value: "Accrochage au feu rouge", status: "a_verifier" },
      { label: "Dommages", value: "Pare-choc abim\u00e9", status: "a_verifier" },
      { label: "Bless\u00e9s", value: "Non signal\u00e9", status: "confirme" },
      { label: "T\u00e9moins", value: null, status: "manquant" },
    ],
  },
  {
    reference: "SIN-2026-00125",
    assure: "Marie Ang\u00e9",
    telephone: "+225 05 12 34 56 78",
    type: "Assistance automobile",
    date: "2026-08-19",
    agent: "Awa Traor\u00e9",
    statut: "En cours",
    confiance: 58,
    lieu: "Yopougon, Abidjan",
    resume: "Panne moteur sur autoroute, remorquage demande.",
    transcription: [
      { speaker: "assure", text: "Ma voiture est en panne sur l'autoroute a Yopougon." },
      { speaker: "agent", text: "D'accord, je programme un remorquage. Vous etes en securite ?" },
      { speaker: "assure", text: "Oui, je suis sur le bas-cote." },
    ],
    extractedFields: [
      { label: "Nom assur\u00e9", value: "Marie Ang\u00e9", status: "confirme" },
      { label: "T\u00e9l\u00e9phone", value: "+225 05 12 34 56 78", status: "confirme" },
      { label: "Num\u00e9ro contrat", value: null, status: "manquant" },
      { label: "Date", value: "2026-08-19", status: "confirme" },
      { label: "Heure", value: "14:02", status: "confirme" },
      { label: "Lieu", value: "Yopougon, Abidjan", status: "confirme" },
      { label: "Type de sinistre", value: "Assistance automobile", status: "confirme" },
      { label: "V\u00e9hicule", value: null, status: "manquant" },
      { label: "Immatriculation", value: null, status: "manquant" },
      { label: "Circonstances", value: "Panne moteur sur autoroute", status: "confirme" },
      { label: "Dommages", value: null, status: "manquant" },
      { label: "Bless\u00e9s", value: "Non signal\u00e9", status: "confirme" },
      { label: "T\u00e9moins", value: null, status: "manquant" },
    ],
  },
  {
    reference: "SIN-2026-00126",
    assure: "Ibrahim Kon\u00e9",
    telephone: "+225 01 98 76 54 32",
    type: "Assurance sant\u00e9",
    date: "2026-08-18",
    agent: "Serge Bamba",
    statut: "Valide",
    confiance: 91,
    lieu: "-",
    resume: "Demande de remboursement de consultation medicale.",
    transcription: [
      { speaker: "assure", text: "Je voudrais un remboursement pour une consultation medicale." },
      { speaker: "agent", text: "Avez-vous la facture de la consultation ?" },
      { speaker: "assure", text: "Oui, je peux l'envoyer par email." },
    ],
    extractedFields: [
      { label: "Nom assur\u00e9", value: "Ibrahim Kon\u00e9", status: "confirme" },
      { label: "T\u00e9l\u00e9phone", value: "+225 01 98 76 54 32", status: "confirme" },
      { label: "Num\u00e9ro contrat", value: "CT-2023-44210", status: "confirme" },
      { label: "Date", value: "2026-08-18", status: "confirme" },
      { label: "Heure", value: "10:45", status: "confirme" },
      { label: "Lieu", value: "-", status: "confirme" },
      { label: "Type de sinistre", value: "Assurance sant\u00e9", status: "confirme" },
      { label: "V\u00e9hicule", value: "-", status: "confirme" },
      { label: "Immatriculation", value: "-", status: "confirme" },
      { label: "Circonstances", value: "Consultation medicale", status: "confirme" },
      { label: "Dommages", value: "-", status: "confirme" },
      { label: "Bless\u00e9s", value: "-", status: "confirme" },
      { label: "T\u00e9moins", value: "-", status: "confirme" },
    ],
  },
  {
    reference: "SIN-2026-00127",
    assure: "Fatou Diabat\u00e9",
    telephone: "+225 07 45 12 33 90",
    type: "R\u00e9clamation",
    date: "2026-08-17",
    agent: "Serge Bamba",
    statut: "Cloture",
    confiance: 88,
    lieu: "-",
    resume: "Reclamation sur delai de traitement d'un dossier precedent.",
    transcription: [
      { speaker: "assure", text: "Je fais une reclamation sur le delai de traitement de mon dossier." },
      { speaker: "agent", text: "Je transmets votre reclamation au service concerne." },
    ],
    extractedFields: [
      { label: "Nom assur\u00e9", value: "Fatou Diabat\u00e9", status: "confirme" },
      { label: "T\u00e9l\u00e9phone", value: "+225 07 45 12 33 90", status: "confirme" },
      { label: "Num\u00e9ro contrat", value: "CT-2022-11987", status: "confirme" },
      { label: "Date", value: "2026-08-17", status: "confirme" },
      { label: "Heure", value: "16:20", status: "confirme" },
      { label: "Lieu", value: "-", status: "confirme" },
      { label: "Type de sinistre", value: "R\u00e9clamation", status: "confirme" },
      { label: "V\u00e9hicule", value: "-", status: "confirme" },
      { label: "Immatriculation", value: "-", status: "confirme" },
      { label: "Circonstances", value: "D\u00e9lai de traitement jug\u00e9 trop long", status: "confirme" },
      { label: "Dommages", value: "-", status: "confirme" },
      { label: "Bless\u00e9s", value: "-", status: "confirme" },
      { label: "T\u00e9moins", value: "-", status: "confirme" },
    ],
  },
];
