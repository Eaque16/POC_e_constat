import type { ComponentType } from "react";

export interface NavItem {
  label: string;
  path: string;
  icon: ComponentType<{ className?: string }>;
  description?: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}
