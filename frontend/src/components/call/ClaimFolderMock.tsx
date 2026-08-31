import type { MockClaimFolder } from "@/data/mockCall";

interface ClaimFolderMockProps {
  folder: MockClaimFolder;
}

const statusStyles: Record<MockClaimFolder["status"], string> = {
  "\u00c0 v\u00e9rifier": "bg-warning/15 text-warning",
  "Valid\u00e9": "bg-success/15 text-success",
  Nouveau: "bg-primary/10 text-primary",
};

export function ClaimFolderMock({ folder }: ClaimFolderMockProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-muted-foreground">
          {"Dossier sinistre"}
        </h3>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${statusStyles[folder.status]}`}
        >
          {folder.status}
        </span>
      </div>

      <div className="mt-3 space-y-1 text-sm">
        <div className="flex justify-between">
          <span className="text-muted-foreground">{"R\u00e9f\u00e9rence"}</span>
          <span className="font-medium">{folder.reference}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">{"Type"}</span>
          <span className="font-medium">{folder.type}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">{"Confiance IA"}</span>
          <span className="font-medium">{folder.confidence}%</span>
        </div>
      </div>

      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full bg-primary"
          style={{ width: `${folder.confidence}%` }}
        />
      </div>

      {folder.missingFields.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-muted-foreground">
            {"Informations manquantes"}
          </p>
          <ul className="mt-1 space-y-1">
            {folder.missingFields.map((field) => (
              <li
                key={field}
                className="flex items-center gap-1.5 text-xs text-warning"
              >
                {"\u26a0\ufe0f "}
                {field}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
