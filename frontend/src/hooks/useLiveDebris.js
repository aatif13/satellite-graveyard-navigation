import { useCallback, useEffect, useRef, useState } from 'react';

function wsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/api/ws/live`;
}

export function useLiveDebris({ enabled, isroOnly, onUpdate }) {
  const wsRef = useRef(null);
  const isroRef = useRef(isroOnly);
  const retryRef = useRef(null);
  const [connected, setConnected] = useState(false);
  const [lastPush, setLastPush] = useState(null);
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;
  isroRef.current = isroOnly;

  const send = useCallback((msg) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const refresh = useCallback(() => send({ type: 'refresh' }), [send]);

  useEffect(() => {
    if (!enabled) {
      clearTimeout(retryRef.current);
      wsRef.current?.close();
      wsRef.current = null;
      setConnected(false);
      return undefined;
    }

    let attempt = 0;
    let closed = false;

    const connect = () => {
      if (closed) return;
      const ws = new WebSocket(`${wsUrl()}?isro_only=${isroRef.current}`);
      wsRef.current = ws;

      ws.onopen = () => {
        attempt = 0;
        setConnected(true);
        ws.send(JSON.stringify({ type: 'set_filter', isro_only: isroRef.current }));
      };

      ws.onclose = () => {
        setConnected(false);
        if (!closed) {
          const delay = Math.min(30000, 1000 * 2 ** attempt);
          attempt += 1;
          retryRef.current = setTimeout(connect, delay);
        }
      };

      ws.onerror = () => setConnected(false);

      ws.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);
          if (data.type === 'refresh_started') {
            onUpdateRef.current?.({ refreshing: true });
          } else if (data.type === 'connected' || data.type === 'debris_update') {
            setLastPush(data.timestamp || new Date().toISOString());
            onUpdateRef.current?.({
              objects: data.objects || [],
              count: data.count,
              cache_age_s: data.cache_age_s,
              catalog_live: data.catalog_live,
              catalog_source: data.catalog_source,
              refreshing: false,
            });
          }
        } catch {
          /* ignore malformed frames */
        }
      };
    };

    connect();

    return () => {
      closed = true;
      clearTimeout(retryRef.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [enabled]);

  useEffect(() => {
    if (enabled && connected) {
      send({ type: 'set_filter', isro_only: isroOnly });
    }
  }, [enabled, connected, isroOnly, send]);

  return { connected, lastPush, refresh, send };
}
