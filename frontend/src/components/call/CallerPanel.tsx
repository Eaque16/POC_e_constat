import type { MockCaller } from "@/data/mockCall";

interface CallerPanelProps {
  caller: MockCaller;
}

export function CallerPanel({ caller }: CallerPanelProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <h3 className="text-sm font-semibold text-muted-foreground">
        {"Informations appelant"}
      </h3>
      <dl className="mt-3 space-y-2 text-sm">
        <div className="flex justify-between">
          <dt className="text-muted-foreground">{"Nom"}</dt>
          <dd className="font-medium">{caller.name}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">{"T\u00e9l\u00e9phone"}</dt>
          <dd className="font-medium">{caller.phone}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted-foreground">{"Contrat"}</dt>
          <dd className="font-medium">
            {caller.contractNumber ?? "Non identifi\u00e9"}
          </dd>
        </div>
      </dl>
    </div>
  );
}
