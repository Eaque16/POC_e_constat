import { useState } from "react";
import SettingsSection from "../components/settings/SettingsSection";
import type { AppSettings } from "../types/settings";

const defaultSettings: AppSettings = {
  langueInterface: "fr",
  notificationsActives: true,
  transcriptionAutomatique: true,
  suggestionsCopilotActives: true,
  seuilConfianceIA: 75,
};

export default function Settings() {
  const [settings, setSettings] = useState<AppSettings>(defaultSettings);

  const toggle = (key: keyof AppSettings) => {
    setSettings((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="p-6 space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-blue-950">Parametres</h1>
          <p className="text-sm text-gray-500">Preferences de l'application (stockage local pour le moment)</p>
        </div>
        <span className="text-xs font-medium bg-amber-100 text-amber-700 px-2 py-1 rounded-full">
          DEMO
        </span>
      </div>

      <SettingsSection
        title="Assistance IA"
        description="Comportement du copilot et de la transcription pendant les appels"
      >
        <label className="flex items-center justify-between text-sm">
          <span>Transcription automatique</span>
          <input
            type="checkbox"
            checked={settings.transcriptionAutomatique}
            onChange={() => toggle("transcriptionAutomatique")}
            className="w-4 h-4 accent-blue-700"
          />
        </label>
        <label className="flex items-center justify-between text-sm">
          <span>Suggestions du copilot actives</span>
          <input
            type="checkbox"
            checked={settings.suggestionsCopilotActives}
            onChange={() => toggle("suggestionsCopilotActives")}
            className="w-4 h-4 accent-blue-700"
          />
        </label>
        <div className="flex items-center justify-between text-sm">
          <span>Seuil de confiance IA minimum ({settings.seuilConfianceIA}%)</span>
          <input
            type="range"
            min={0}
            max={100}
            value={settings.seuilConfianceIA}
            onChange={(e) =>
              setSettings((prev) => ({ ...prev, seuilConfianceIA: Number(e.target.value) }))
            }
            className="w-40 accent-blue-700"
          />
        </div>
      </SettingsSection>

      <SettingsSection title="Notifications">
        <label className="flex items-center justify-between text-sm">
          <span>Notifications actives</span>
          <input
            type="checkbox"
            checked={settings.notificationsActives}
            onChange={() => toggle("notificationsActives")}
            className="w-4 h-4 accent-blue-700"
          />
        </label>
      </SettingsSection>

      <SettingsSection title="Langue de l'interface">
        <select
          value={settings.langueInterface}
          onChange={(e) =>
            setSettings((prev) => ({
              ...prev,
              langueInterface: e.target.value as "fr" | "en",
            }))
          }
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 w-full"
        >
          <option value="fr">Francais</option>
          <option value="en">English</option>
        </select>
      </SettingsSection>
    </div>
  );
}