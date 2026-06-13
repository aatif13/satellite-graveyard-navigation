import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchDebris } from '../api';
import { wsLiveUrl } from '../config';

export function useLiveDebris({ enabled, isroOnly, onUpdate }) {
  const wsRef = useRef(null);
  const isroRef = useRef(isroOnly);
  const retryRef = useRef(null);
  const fetchRef = useRef(0);
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

  const loadCatalog = useCallback(async (meta) => {
    const reqId = ++fetchRef.current;
    try {
      const full = await fetchDebris({ isroOnly: isroRef.current });
      if (reqId !== fetchRef.current) return;
      onUpdateRef.current?.({
        objects: full.objects || [],
        count: full.count,
        cache_age_s: full.cache_age_s,
        catalog_live: full.catalog_live,
        catalog_source: full.catalog_source,
        refreshing: false,
      });
    } catch {
      if (reqId !== fetchRef.current) return;
      onUpdateRef.current?.({
        objects: meta?.objects || [],
        count: meta?.count ?? 0,
        cache_age_s: meta?.cache_age_s,
        catalog_live: meta?.catalog_live,
        catalog_source: meta?.catalog_source,
        refreshing: false,
      });
    }
  }, []);

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
      const ws = new WebSocket(`${wsLiveUrl()}?isro_only=${isroRef.current}`);
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
            if (data.objects?.length) {
              onUpdateRef.current?.({
                objects: data.objects,
                count: data.count,
                cache_age_s: data.cache_age_s,
                catalog_live: data.catalog_live,
                catalog_source: data.catalog_source,
                refreshing: false,
              });
            } else {
              loadCatalog(data);
            }
          }
        } catch {
          /* ignore malformed frames */
        }
      };
    };

    connect();

    return () => {
      closed = true;
      fetchRef.current += 1;
      clearTimeout(retryRef.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [enabled, loadCatalog]);

  useEffect(() => {
    if (enabled && connected) {
      send({ type: 'set_filter', isro_only: isroOnly });
    }
  }, [enabled, connected, isroOnly, send]);

  return { connected, lastPush, refresh, send };
}
