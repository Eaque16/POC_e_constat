export function LiveConversationPlaceholder() {
  return (
    <div className="flex h-full flex-col rounded-xl border border-border bg-card p-4">
      <h3 className="text-sm font-semibold text-muted-foreground">
        Conversation live
      </h3>
      <div className="mt-3 flex flex-1 items-center justify-center rounded-lg border border-dashed border-border bg-muted/30 text-sm text-muted-foreground">
        \ud83c\udf99\ufe0f Transcription en temps r\u00e9el - construit en Phase 3
      </div>
    </div>
  );
}
