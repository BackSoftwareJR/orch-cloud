"use client";

import { FolderKanban, LayoutDashboard, ListTodo, Settings } from "lucide-react";
import Link from "next/link";

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
    <nav className="mobile-nav z-40 lg:hidden" aria-label="Main navigation">
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
      <Link href="/settings" className="mobile-nav-item" aria-label="Settings">
        <Settings className="h-5 w-5" />
        <span>Settings</span>
      </Link>
    </nav>
  );
}
