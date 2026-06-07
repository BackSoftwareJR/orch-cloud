"use client";

import { Bot, Loader2, User } from "lucide-react";
import { useEffect, useRef } from "react";

import type { JobMessage } from "@/lib/types";

interface TaskChatProps {
  messages: JobMessage[];
  loading?: boolean;
}

function roleMeta(role: JobMessage["role"]) {
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
        icon: <Bot className="h-3.5 w-3.5" />,
        bubble: "chat-bubble-system",
        align: "items-start",
      };
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

export function TaskChat({ messages, loading = false }: TaskChatProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, loading]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="scrollbar-thin flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {loading && messages.length === 0 ? (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-zinc-500">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading conversation…
          </div>
        ) : messages.length === 0 ? (
          <p className="py-16 text-center text-sm text-zinc-500">
            No messages yet. The task prompt will appear here once loaded.
          </p>
        ) : (
          messages.map((message) => {
            const meta = roleMeta(message.role);
            return (
              <div key={message.id} className={`flex flex-col ${meta.align} gap-1`}>
                <div className="flex items-center gap-2 px-1 text-[10px] uppercase tracking-wider text-zinc-500">
                  {meta.icon}
                  {meta.label}
                  <span>·</span>
                  <span>{formatTime(message.created_at)}</span>
                </div>
                <div className={`max-w-[92%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed ${meta.bubble}`}>
                  {message.content}
                </div>
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
