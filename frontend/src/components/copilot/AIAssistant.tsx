import { useState } from "react";
import type { Suggestion, AnalysisBadge, BadgeKind } from "@/hooks/useCallAnalysis";

interface AIAssistantProps {
  suggestion: Suggestion | null;
  badges: AnalysisBadge[];
  extraQuestion: string | null;
}

const badgeStyles: Record<BadgeKind, { icon: string; className: string }> = {
  detected: { icon: "\ud83d\udfe2", className: "bg-success/10 text-success" },
  missing: { icon: "\ud83d\udfe1", className: "bg-warning/10 text-warning" },
  question: { icon: "\ud83d\udd35", className: "bg-primary/10 text-primary" },
  urgent: { icon: "\ud83d\udd34", className: "bg-destructive/10 text-destructive" },
};

export function AIAssistant({ suggestion, badges, extraQuestion }: AIAssistantProps) {
  const [used, setUsed] = useState<string[]>([]);
  const [ignored, setIgnored] = useState<string[]>([]);

  const activeText = extraQuestion ?? suggestion?.text ?? null;
  const activeId = extraQuestion ? "extra" : suggestion?.id ?? null;

  return (
    <div className="flex h-full flex-col rounded-xl border border-border bg-card p-4">
      <h3 className="text-sm font-semibold text-muted-foreground">
        {"\ud83e\udd16 ASA AI Copilot"}
      </h3>

      <div className="mt-3 flex-1 space-y-4 overflow-y-auto">
        <div>
          <p className="text-xs font-medium text-muted-foreground">
            {"R\u00e9ponse sugg\u00e9r\u00e9e"}
          </p>
          {activeText ? (
            <div className="mt-1 rounded-lg bg-muted/50 p-3 text-sm">
              {"\u201c"}
              {activeText}
              {"\u201d"}
              {activeId && !used.includes(activeId) && !ignored.includes(activeId) && (
                <div className="mt-2 flex gap-2">
                  <button
                    onClick={() => setUsed((prev) => [...prev, activeId])}
                    className="rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground"
                  >
                    {"Utiliser"}
                  </button>
                  <button
                    className="rounded-md border border-border px-2.5 py-1 text-xs font-medium"
                  >
                    {"Modifier"}
                  </button>
                  <button
                    onClick={() => setIgnored((prev) => [...prev, activeId])}
                    className="rounded-md px-2.5 py-1 text-xs font-medium text-muted-foreground"
                  >
                    {"Ignorer"}
                  </button>
                </div>
              )}
              {activeId && used.includes(activeId) && (
                <p className="mt-2 text-xs font-medium text-success">
                  {"\u2713 Utilis\u00e9e par l'agent"}
                </p>
              )}
              {activeId && ignored.includes(activeId) && (
                <p className="mt-2 text-xs font-medium text-muted-foreground">
                  {"Ignor\u00e9e"}
                </p>
              )}
            </div>
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">
              {"En attente de la conversation..."}
            </p>
          )}
        </div>

        {badges.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground">
              {"Informations d\u00e9tect\u00e9es"}
            </p>
            <ul className="mt-1 space-y-1.5">
              {badges.map((badge) => (
                <li
                  key={badge.id}
                  className={`flex items-center gap-2 rounded-md px-2 py-1 text-xs font-medium ${badgeStyles[badge.kind].className}`}
                >
                  <span>{badgeStyles[badge.kind].icon}</span>
                  {badge.label}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
