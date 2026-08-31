import {
  LayoutDashboard,
  Phone,
  Bot,
  FolderOpen,
  Car,
  HeartPulse,
  BarChart3,
  Users,
  Settings,
  Database,
} from "lucide-react";
import type { NavGroup } from "@/types/navigation";

export const navGroups: NavGroup[] = [
  {
    label: "Vue d’ensemble",
    items: [{ label: "Accueil", path: "/", icon: LayoutDashboard }],
  },
  {
    label: "Opérations",
    items: [
      { label: "Poste d’appel", path: "/appels", icon: Phone },
      { label: "Assistant IA", path: "/assistant-ia", icon: Bot },
      { label: "Dossiers", path: "/dossiers", icon: FolderOpen },
      { label: "Sinistres auto", path: "/sinistres", icon: Car },
      { label: "Assurance santé", path: "/sante", icon: HeartPulse },
    ],
  },
  {
    label: "Données & analyses",
    items: [
      { label: "Explorateur de données", path: "/donnees", icon: Database },
      { label: "Statistiques", path: "/statistiques", icon: BarChart3 },
    ],
  },
  {
    label: "Administration",
    items: [
      { label: "Agents", path: "/agents", icon: Users },
      { label: "Paramètres", path: "/parametres", icon: Settings },
    ],
  },
];
