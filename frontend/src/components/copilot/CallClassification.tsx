import type { ClassificationResult } from "@/hooks/useCallAnalysis";

interface CallClassificationProps {
  classification: ClassificationResult;
}

export function CallClassification({ classification }: CallClassificationProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <h3 className="text-sm font-semibold text-muted-foreground">
        {"Classification"}
      </h3>
      <div className="mt-2 flex items-center justify-between">
        <span className="text-sm font-medium">{classification.category}</span>
        <span className="text-sm font-semibold text-primary">
          {classification.confidence}%
        </span>
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full bg-primary transition-all"
          style={{ width: `${classification.confidence}%` }}
        />
      </div>
    </div>
  );
}
