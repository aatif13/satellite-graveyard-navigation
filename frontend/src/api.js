import { apiUrl } from './config';

const API = () => apiUrl('/api');

export async function fetchDebris({ isroOnly = false, refresh = false } = {}) {
  const params = new URLSearchParams();
  if (isroOnly) params.set('isro_only', 'true');
  if (refresh) params.set('refresh', 'true');
  const res = await fetch(`${API()}/debris?${params}`);
  if (!res.ok) throw new Error('Failed to fetch debris');
  return res.json();
}

export async function fetchHeatmap() {
  const res = await fetch(`${API()}/heatmap`);
  if (!res.ok) throw new Error('Failed to fetch heatmap');
  return res.json();
}

export async function fetchIsroConstellation() {
  const res = await fetch(`${API()}/isro/constellation`);
  if (!res.ok) throw new Error('Failed to fetch ISRO data');
  return res.json();
}

export async function analyzeOrbit(waypoints, targetAltKm, debrisObjects = null) {
  const body = { waypoints, target_alt_km: targetAltKm };
  if (debrisObjects?.length) {
    body.debris_objects = debrisObjects;
  }
  const res = await fetch(`${API()}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Analysis failed');
  return res.json();
}

export async function fetchPresets() {
  const res = await fetch(`${API()}/presets`);
  if (!res.ok) throw new Error('Failed to fetch presets');
  return res.json();
}

export async function aiPlanMission(query) {
  const res = await fetch(`${API()}/ai/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) throw new Error('AI planning failed');
  return res.json();
}

export async function fetchHealth() {
  const res = await fetch(`${API()}/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}
