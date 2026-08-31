interface PagePlaceholderProps {
  title: string;
  description: string;
}

export function PagePlaceholder({ title, description }: PagePlaceholderProps) {
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-bold text-foreground">{title}</h1>
      <p className="text-sm text-muted-foreground">{description}</p>
      <div className="mt-6 flex h-48 items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 text-sm text-muted-foreground">
        {"\u00c0 construire dans une phase suivante"}
      </div>
    </div>
  );
}
