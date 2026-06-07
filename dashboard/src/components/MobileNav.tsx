"use client";

import { FolderKanban, LayoutDashboard, ListTodo } from "lucide-react";

export type MobilePanel = "projects" | "tasks" | "workspace";

interface MobileNavProps {
  active: MobilePanel;
  onChange: (panel: MobilePanel) => void;
  hasWorkspace: boolean;
}

const ITEMS: { id: MobilePanel; label: string; icon: typeof FolderKanban }[] = [
  { id: "projects", label: "Projects", icon: FolderKanban },
  { id: "tasks", label: "Tasks", icon: ListTodo },
  { id: "workspace", label: "Chat", icon: LayoutDashboard },
];

export function MobileNav({ active, onChange, hasWorkspace }: MobileNavProps) {
  return (
    <nav className="mobile-nav lg:hidden">
      {ITEMS.map((item) => {
        const Icon = item.icon;
        const disabled = item.id === "workspace" && !hasWorkspace;
        const isActive = active === item.id;
        return (
          <button
            key={item.id}
            type="button"
            disabled={disabled}
            onClick={() => onChange(item.id)}
            className={`mobile-nav-item ${isActive ? "mobile-nav-item-active" : ""} ${
              disabled ? "opacity-40" : ""
            }`}
          >
            <Icon className="h-5 w-5" />
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
