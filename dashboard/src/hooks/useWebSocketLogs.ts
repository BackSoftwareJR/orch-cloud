"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getWebSocketUrl } from "@/lib/api";

interface UseWebSocketLogsOptions {
  jobId: string | null;
  enabled?: boolean;
}

interface UseWebSocketLogsResult {
  lines: string;
  connected: boolean;
  error: string | null;
  clear: () => void;
}

export function useWebSocketLogs({
  jobId,
  enabled = true,
}: UseWebSocketLogsOptions): UseWebSocketLogsResult {
  const [lines, setLines] = useState("");
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const clear = useCallback(() => setLines(""), []);

  useEffect(() => {
    if (!jobId || !enabled) {
      setConnected(false);
      return;
    }

    const url = getWebSocketUrl(jobId);
    const socket = new WebSocket(url);
    socketRef.current = socket;

    socket.onopen = () => {
      setConnected(true);
      setError(null);
    };

    socket.onmessage = (event) => {
      setLines((prev) => prev + String(event.data));
    };

    socket.onerror = () => {
      setError("WebSocket connection error");
      setConnected(false);
    };

    socket.onclose = () => {
      setConnected(false);
    };

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [jobId, enabled]);

  return { lines, connected, error, clear };
}
