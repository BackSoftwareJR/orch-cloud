import type { AgentPresetInfo, ModelInfo, ModelProvider } from "./types";

export const TRIGGER_SELECTION_KEY = "hyperorch:trigger-selection";

export interface TriggerSelection {
  preset: string;
  level: string;
  model: string;
}

/** Backend ModelResponse shape from GET /models */
export interface ModelResponseDto {
  slug: string;
  label: string;
  tier: "composer" | "api" | string;
  description: string;
}

const PRESET_DEFAULT_MODELS: Record<string, string> = {
  general: "composer-2.5",
  ux: "composer-2.5",
  backend: "claude-4.6-sonnet-medium-thinking",
  bugfix: "claude-4-sonnet",
};

function providerForSlug(slug: string, tier: string): ModelProvider {
  if (tier === "composer") return "cursor";
  if (slug.startsWith("gpt")) return "openai";
  return "anthropic";
}

function presetsForModel(slug: string, tier: string): string[] {
  if (tier === "composer") return ["general", "ux", "backend", "bugfix"];
  if (slug.startsWith("gpt")) return ["backend", "general", "bugfix"];
  return ["backend", "general", "bugfix"];
}

function defaultForModel(slug: string): string[] {
  return Object.entries(PRESET_DEFAULT_MODELS)
    .filter(([, model]) => model === slug)
    .map(([preset]) => preset);
}

export function mapModelResponse(dto: ModelResponseDto): ModelInfo {
  const provider = providerForSlug(dto.slug, dto.tier);
  return {
    id: dto.slug,
    label: dto.label,
    description: dto.description,
    provider,
    billing: dto.tier === "composer" ? "included" : "api_credits",
    presets: presetsForModel(dto.slug, dto.tier),
    default_for: defaultForModel(dto.slug),
  };
}

export function mapModelResponses(dtos: ModelResponseDto[]): ModelInfo[] {
  return dtos.map(mapModelResponse);
}

export const FALLBACK_MODELS: ModelInfo[] = mapModelResponses([
  {
    slug: "composer-2.5",
    label: "Composer 2.5",
    tier: "composer",
    description: "Fast Cursor composer model for UI and general coding tasks.",
  },
  {
    slug: "claude-4-sonnet",
    label: "Claude 4 Sonnet",
    tier: "api",
    description: "Balanced reasoning model for debugging and focused fixes.",
  },
  {
    slug: "claude-4.5-sonnet-thinking",
    label: "Claude 4.5 Sonnet (Thinking)",
    tier: "api",
    description: "Extended reasoning for complex multi-file changes.",
  },
  {
    slug: "claude-4.6-sonnet-medium-thinking",
    label: "Claude 4.6 Sonnet (Medium Thinking)",
    tier: "api",
    description: "Strong backend reasoning with moderate thinking depth.",
  },
  {
    slug: "claude-4.6-opus-high-thinking",
    label: "Claude 4.6 Opus (High Thinking)",
    tier: "api",
    description: "Deep reasoning for architecture and hard backend problems.",
  },
  {
    slug: "claude-opus-4-7-thinking-xhigh",
    label: "Claude Opus 4.7 (XHigh Thinking)",
    tier: "api",
    description: "Maximum reasoning depth for the hardest tasks.",
  },
  {
    slug: "claude-opus-4-8-thinking-high",
    label: "Claude Opus 4.8 (High Thinking)",
    tier: "api",
    description: "Latest Opus with high thinking for production-grade work.",
  },
  {
    slug: "gpt-5.3-codex",
    label: "GPT-5.3 Codex",
    tier: "api",
    description: "OpenAI Codex-class model for code generation.",
  },
  {
    slug: "gpt-5.5-medium",
    label: "GPT-5.5 Medium",
    tier: "api",
    description: "General-purpose GPT model with balanced speed and quality.",
  },
]);

export function modelLabel(id: string | undefined | null, models: ModelInfo[] = FALLBACK_MODELS): string {
  if (!id) return "Composer 2.5";
  const match = models.find((model) => model.id === id);
  return match?.label ?? id;
}

export function filterModelsForPreset(models: ModelInfo[], presetId: string): ModelInfo[] {
  const filtered = models.filter((model) => model.presets.includes(presetId));
  return filtered.length > 0 ? filtered : models;
}

export function defaultModelForPreset(models: ModelInfo[], presetId: string): string {
  const filtered = filterModelsForPreset(models, presetId);
  const preferred = filtered.find((model) => model.default_for?.includes(presetId));
  return preferred?.id ?? filtered[0]?.id ?? FALLBACK_MODELS[0].id;
}

export function resolveJobModel(
  job: { model?: string | null; preset?: string },
  models: ModelInfo[] = FALLBACK_MODELS,
): string {
  if (job.model) return job.model;
  return defaultModelForPreset(models, job.preset ?? "general");
}

export function isApiCreditsModel(modelId: string, models: ModelInfo[] = FALLBACK_MODELS): boolean {
  const model = models.find((item) => item.id === modelId);
  return model?.billing === "api_credits";
}

export function loadTriggerSelection(): TriggerSelection | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(TRIGGER_SELECTION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as TriggerSelection;
    if (!parsed.preset || !parsed.level || !parsed.model) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveTriggerSelection(selection: TriggerSelection): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(TRIGGER_SELECTION_KEY, JSON.stringify(selection));
  } catch {
    // Ignore quota / private mode errors
  }
}

export function applyPresetDefaults(
  preset: AgentPresetInfo,
  models: ModelInfo[],
  currentModel: string,
): { level: string; model: string } {
  const compatible = filterModelsForPreset(models, preset.id);
  const modelStillValid = compatible.some((item) => item.id === currentModel);
  return {
    level: preset.default_level,
    model: modelStillValid
      ? currentModel
      : (preset.default_model ?? defaultModelForPreset(models, preset.id)),
  };
}
