"use client";

import { Bot, Loader2, Radio, User, Zap } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import type { LiveFeedItem, LiveLogLevel } from "@/lib/logStream";

interface TaskChatProps {
  items: LiveFeedItem[];
  loading?: boolean;
  streaming?: boolean;
  connected?: boolean;
}

function roleMeta(role: LiveFeedItem["role"]) {
  switch (role) {
    case "user":
      return {
        label: "You",
        icon: <User className="h-3.5 w-3.5" />,
        bubble: "chat-bubble-user",
        align: "items-end",
      };
    case "assistant":
      return {
        label: "Agent",
        icon: <Bot className="h-3.5 w-3.5" />,
        bubble: "chat-bubble-assistant",
        align: "items-start",
      };
    default:
      return {
        label: "System",
        icon: <Zap className="h-3.5 w-3.5" />,
        bubble: "chat-bubble-system",
        align: "items-start",
      };
  }
}

function liveLevelClass(level?: LiveLogLevel): string {
  switch (level) {
    case "error":
      return "chat-live-error";
    case "warn":
      return "chat-live-warn";
    case "success":
      return "chat-live-success";
    default:
      return "chat-live-info";
  }
}

function formatTime(value: string): string {
  return new Date(value).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function TaskChat({
  items,
  loading = false,
  streaming = false,
  connected = false,
}: TaskChatProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [stickToBottom, setStickToBottom] = useState(true);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior });
  }, []);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setStickToBottom(distanceFromBottom < 80);
  }, []);

  useEffect(() => {
    if (stickToBottom) {
      scrollToBottom(items.length > 3 ? "smooth" : "auto");
    }
  }, [items, stickToBottom, scrollToBottom]);

  return (
    <div className="relative flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex shrink-0 items-center justify-between border-b border-white/[0.04] px-4 py-2 lg:px-5">
        <span className="text-xs font-medium text-zinc-400">Conversation</span>
        <span className="inline-flex items-center gap-1.5 text-[10px] text-zinc-500">
          <Radio className={`h-3 w-3 ${connected ? "text-emerald-400 animate-pulse" : "text-zinc-600"}`} />
          {streaming ? (connected ? "Live" : "Connecting…") : "Idle"}
        </span>
      </div>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="workspace-scroll scrollbar-thin space-y-3 px-4 py-4 lg:space-y-4 lg:px-5"
      >
        {loading && items.length === 0 ? (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-zinc-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading conversation…
          </div>
        ) : items.length === 0 ? (
          <p className="py-16 text-center text-sm text-zinc-500">
            Live updates from the orchestrator will appear here as the task runs.
          </p>
        ) : (
          items.map((item) => {
            if (item.kind === "live") {
              return (
                <div key={item.id} className="flex flex-col items-start gap-1 live-feed-enter">
                  <div className="flex items-center gap-2 px-1 text-[10px] uppercase tracking-wider text-zinc-500">
                    <span className="live-dot" />
                    Live
                    <span>·</span>
                    <span>{formatTime(item.timestamp)}</span>
                  </div>
                  <div
                    className={`max-w-[96%] whitespace-pre-wrap rounded-xl px-3 py-2 font-mono text-[11px] leading-relaxed lg:max-w-[92%] lg:rounded-2xl lg:px-4 lg:py-2.5 lg:text-xs ${liveLevelClass(item.level)}`}
                  >
                    {item.content}
                  </div>
                </div>
              );
            }

            const meta = roleMeta(item.role);
            return (
              <div key={item.id} className={`flex flex-col ${meta.align} gap-1`}>
                <div className="flex items-center gap-2 px-1 text-[10px] uppercase tracking-wider text-zinc-500">
                  {meta.icon}
                  {meta.label}
                  <span>·</span>
                  <span>{formatTime(item.timestamp)}</span>
                </div>
                <div
                  className={`max-w-[96%] whitespace-pre-wrap rounded-2xl px-3 py-2.5 text-sm leading-relaxed lg:max-w-[92%] lg:px-4 lg:py-3 ${meta.bubble}`}
                >
                  {item.content}
                </div>
              </div>
            );
          })
        )}
      </div>

      {!stickToBottom && (
        <button
          type="button"
          onClick={() => {
            setStickToBottom(true);
            scrollToBottom();
          }}
          className="absolute bottom-3 left-1/2 z-10 -translate-x-1/2 rounded-full border border-white/10 bg-zinc-900/90 px-3 py-1 text-[10px] text-zinc-300 shadow-lg backdrop-blur-sm"
        >
          ↓ New messages
        </button>
      )}
    </div>
  );
}
