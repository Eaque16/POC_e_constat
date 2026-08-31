import type { ExtractedField } from "@/hooks/useCallAnalysis";

interface MissingInformationProps {
  fields: ExtractedField[];
  onAskAbout: (label: string) => void;
}

export function MissingInformation({ fields, onAskAbout }: MissingInformationProps) {
  const missing = fields.filter((f) => f.status === "manquant");

  if (missing.length === 0) return null;

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <h3 className="text-sm font-semibold text-muted-foreground">
        {"Informations manquantes"}
      </h3>
      <ul className="mt-2 space-y-1.5">
        {missing.map((field) => (
          <li key={field.key}>
            <button
              onClick={() =>
                onAskAbout(`Pouvez-vous me donner : ${field.label} ?`)
              }
              className="flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-xs font-medium text-warning transition hover:bg-warning/10"
            >
              {"\u26a0\ufe0f "}
              {field.label}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
