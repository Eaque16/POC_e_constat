import type { ReactNode } from "react";

interface SettingsSectionProps {
  title: string;
  description?: string;
  children: ReactNode;
}

export default function SettingsSection({ title, description, children }: SettingsSectionProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-blue-950">{title}</h2>
        {description && <p className="text-xs text-gray-500 mt-0.5">{description}</p>}
      </div>
      <div className="space-y-3">{children}</div>
    </div>
  );
}