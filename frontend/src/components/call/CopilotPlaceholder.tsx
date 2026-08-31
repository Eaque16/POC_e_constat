export function CopilotPlaceholder() {
  return (
    <div className="flex h-full flex-col rounded-xl border border-border bg-card p-4">
      <h3 className="text-sm font-semibold text-muted-foreground">
        {"\ud83e\udd16 ASA AI Copilot"}
      </h3>
      <div className="mt-3 flex flex-1 items-center justify-center rounded-lg border border-dashed border-border bg-muted/30 text-sm text-muted-foreground">
        {"Suggestions, classification et extraction - construit en Phase 4"}
      </div>
    </div>
  );
}
