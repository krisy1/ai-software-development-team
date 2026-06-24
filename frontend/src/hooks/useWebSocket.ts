import { useEffect, useRef, useCallback, useState } from 'react';

type WebSocketMessage = Record<string, unknown>;

interface UseWebSocketOptions {
  onMessage?: (data: WebSocketMessage) => void;
  reconnectInterval?: number;
  maxRetries?: number;
}

export function useWebSocket(
  url: string | null,
  options: UseWebSocketOptions = {}
) {
  const {
    onMessage,
    reconnectInterval = 3000,
    maxRetries = 10,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);
  const [connected, setConnected] = useState(false);

  const connect = useCallback(() => {
    if (!url || retryCountRef.current >= maxRetries) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      retryCountRef.current = 0;
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WebSocketMessage;
        onMessage?.(data);
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      if (retryCountRef.current < maxRetries) {
        retryCountRef.current += 1;
        setTimeout(connect, reconnectInterval);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [url, onMessage, reconnectInterval, maxRetries]);

  useEffect(() => {
    connect();
    return () => {
      retryCountRef.current = maxRetries;
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect, maxRetries]);

  return { connected };
}
