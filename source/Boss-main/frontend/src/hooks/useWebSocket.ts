import { useEffect, useRef, useState, useCallback } from "react";

export interface WSEvent {
  event_type: string;
  message: string;
  data: Record<string, unknown>;
  timestamp: string;
}

/**
 * Hook to subscribe to real-time task progress via WebSocket.
 */
export function useTaskWebSocket(taskId: number | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const [events, setEvents] = useState<WSEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    setEvents([]);

    if (!taskId) {
      setConnected(false);
      wsRef.current?.close();
      wsRef.current = null;
      return;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/ws/tasks/${taskId}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;
    let isActive = true;

    ws.onopen = () => {
      if (isActive) {
        setConnected(true);
      }
    };
    ws.onclose = () => {
      if (isActive) {
        setConnected(false);
      }
    };
    ws.onerror = () => {
      if (isActive) {
        setConnected(false);
      }
    };

    ws.onmessage = (msg) => {
      try {
        const event: WSEvent = JSON.parse(msg.data);
        if (isActive) {
          setEvents((prev) => [...prev.slice(-200), event]); // Keep last 200
        }
      } catch {
        // ignore non-JSON messages
      }
    };

    // Ping to keep alive
    const interval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 30_000);

    return () => {
      isActive = false;
      clearInterval(interval);
      ws.close();
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
    };
  }, [taskId]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, connected, clearEvents };
}
