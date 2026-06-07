/** Parse orchestrator log lines into chat-friendly live events. */

export type LiveLogLevel = "info" | "warn" | "error" | "success" | "dim";

export interface ParsedLogLine {
  text: string;
  level: LiveLogLevel;
  raw: string;
}

export interface LiveFeedItem {
  id: string;
  kind: "message" | "live";
  role?: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  level?: LiveLogLevel;
}

function mapLevel(raw: string): LiveLogLevel {
  const upper = raw.toUpperCase();
  if (upper === "ERROR" || upper === "CRITICAL") return "error";
  if (upper === "WARNING" || upper === "WARN") return "warn";
  if (upper === "SUCCESS") return "success";
  return "info";
}

function classifyPlainLine(line: string): LiveLogLevel {
  const lower = line.toLowerCase();
  if (lower.includes("error") || lower.includes("failed") || lower.includes("exception")) {
    return "error";
  }
  if (lower.includes("warn")) return "warn";
  if (lower.includes("completed") || lower.includes("success")) return "success";
  if (line.startsWith("Command:") || line.startsWith("Started:") || line.startsWith("Exit code:")) {
    return "dim";
  }
  return "info";
}

export function parseLogLine(line: string): ParsedLogLine | null {
  const trimmed = line.trim();
  if (!trimmed) return null;

  if (trimmed.startsWith("{")) {
    try {
      const payload = JSON.parse(trimmed) as {
        level?: string;
        message?: string;
        logger?: string;
        event?: string;
        from_model?: string;
        to_model?: string;
        reason?: string;
      };
      if (payload.event === "model_switch") {
        const fromModel = payload.from_model ?? "?";
        const toModel = payload.to_model ?? "?";
        const reason = payload.reason ?? "agent_failure";
        return {
          text: `Model failover: ${fromModel} → ${toModel} (${reason})`,
          level: "warn",
          raw: trimmed,
        };
      }
      if (payload.message) {
        const level = mapLevel(payload.level ?? "INFO");
        const prefix = payload.logger ? `[${payload.logger}] ` : "";
        return {
          text: `${prefix}${payload.message}`,
          level,
          raw: trimmed,
        };
      }
    } catch {
      // fall through to plain text
    }
  }

  if (trimmed.startsWith("[system]")) {
    return { text: trimmed.replace(/^\[system\]\s*/, ""), level: "info", raw: trimmed };
  }

  return {
    text: trimmed,
    level: classifyPlainLine(trimmed),
    raw: trimmed,
  };
}

/** Keep chat readable — skip noisy duplicate git command success lines. */
export function shouldShowInChat(parsed: ParsedLogLine): boolean {
  if (parsed.level === "dim") return false;
  if (parsed.text.includes("Git command succeeded")) return false;
  if (parsed.text.includes("Git command:")) return false;
  return true;
}

export function extractNewLiveLines(
  fullLog: string,
  seenCount: number,
): { items: ParsedLogLine[]; nextSeenCount: number } {
  const lines = fullLog.split("\n");
  const newLines = lines.slice(seenCount);
  const items: ParsedLogLine[] = [];

  for (const line of newLines) {
    const parsed = parseLogLine(line);
    if (parsed && shouldShowInChat(parsed)) {
      items.push(parsed);
    }
  }

  return { items, nextSeenCount: lines.length };
}
