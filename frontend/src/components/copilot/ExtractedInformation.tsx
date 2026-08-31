import type { ExtractedField } from "@/hooks/useCallAnalysis";

interface ExtractedInformationProps {
  fields: ExtractedField[];
}

const statusIcon: Record<ExtractedField["status"], string> = {
  confirme: "\ud83d\udfe2",
  a_verifier: "\ud83d\udfe1",
  manquant: "\ud83d\udd34",
};

export function ExtractedInformation({ fields }: ExtractedInformationProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <h3 className="text-sm font-semibold text-muted-foreground">
        {"Informations extraites"}
      </h3>
      <ul className="mt-2 space-y-1.5">
        {fields.map((field) => (
          <li key={field.key} className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">{field.label}</span>
            <span className="flex items-center gap-1.5 font-medium">
              {statusIcon[field.status]}
              {field.value ?? "-"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
