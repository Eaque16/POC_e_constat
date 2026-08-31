export interface IvrOption {
  key: string;
  label: string;
  outcome: "agent" | "declare";
}

export const ivrScript = "Bienvenue chez ASA-CI TECHNOLOGIE.";

export const ivrOptions: IvrOption[] = [
  { key: "1", label: "Joindre un assistant", outcome: "agent" },
  { key: "2", label: "D\u00e9clarer un sinistre", outcome: "declare" },
];
