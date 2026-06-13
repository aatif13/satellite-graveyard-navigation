/** Production API base — Render backend. Override with VITE_API_BASE_URL on Vercel. */
const RENDER_API = 'https://satellite-graveyard-navigation.onrender.com';

export const API_BASE = (import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? RENDER_API : ''))
  .replace(/\/$/, '');

export function apiUrl(path) {
  const suffix = path.startsWith('/') ? path : `/${path}`;
  return API_BASE ? `${API_BASE}${suffix}` : suffix;
}

export function wsLiveUrl() {
  if (API_BASE) {
    const base = new URL(API_BASE);
    base.protocol = base.protocol === 'https:' ? 'wss:' : 'ws:';
    base.pathname = '/api/ws/live';
    base.search = '';
    base.hash = '';
    return `${base.origin}${base.pathname}`;
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/api/ws/live`;
}
