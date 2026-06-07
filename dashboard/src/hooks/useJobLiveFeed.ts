"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { useWebSocketLogs } from "@/hooks/useWebSocketLogs";
import { extractNewLiveLines, type LiveFeedItem } from "@/lib/logStream";
import type { JobMessage } from "@/lib/types";

interface UseJobLiveFeedOptions {
  jobId: string | null;
  messages: JobMessage[];
  streamEnabled?: boolean;
}

export function useJobLiveFeed({
  jobId,
  messages,
  streamEnabled = true,
}: UseJobLiveFeedOptions) {
  const { lines, connected, error } = useWebSocketLogs({
    jobId,
    enabled: streamEnabled && Boolean(jobId),
  });

  const [liveItems, setLiveItems] = useState<LiveFeedItem[]>([]);
  const seenLineCountRef = useRef(0);

  useEffect(() => {
    seenLineCountRef.current = 0;
    setLiveItems([]);
  }, [jobId]);

  useEffect(() => {
    if (!lines) return;
    const { items, nextSeenCount } = extractNewLiveLines(lines, seenLineCountRef.current);
    seenLineCountRef.current = nextSeenCount;
    if (items.length === 0) return;

    const now = new Date().toISOString();
    setLiveItems((prev) => [
      ...prev,
      ...items.map((item, index) => ({
        id: `live-${nextSeenCount}-${index}-${item.raw.slice(0, 24)}`,
        kind: "live" as const,
        role: "system" as const,
        content: item.text,
        timestamp: now,
        level: item.level,
      })),
    ]);
  }, [lines]);

  const feed = useMemo(() => {
    const staticItems: LiveFeedItem[] = messages.map((message) => ({
      id: `msg-${message.id}`,
      kind: "message",
      role: message.role,
      content: message.content,
      timestamp: message.created_at,
    }));
    return [...staticItems, ...liveItems];
  }, [messages, liveItems]);

  return { feed, lines, connected, error };
}
