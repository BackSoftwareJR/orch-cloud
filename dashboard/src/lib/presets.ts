export const PRESET_LABELS: Record<string, string> = {
  general: "General",
  ux: "UX / UI",
  backend: "Backend",
  bugfix: "Bug Fix",
};

export function presetLabel(id: string | undefined | null): string {
  if (!id) return "General";
  return PRESET_LABELS[id] ?? id;
}
