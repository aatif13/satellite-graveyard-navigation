import { Activity, Layers, Map, Radio, Wifi } from 'lucide-react';

export default function GlobeHUD({ objectCount, wsConnected, liveTracking, catalogLive, altitude, viewMode }) {
  const liveLabel = (() => {
    if (!liveTracking) return 'Paused';
    if (catalogLive && wsConnected) return 'Live';
    if (catalogLive && objectCount > 0) return 'Live (HTTP)';
    if (wsConnected) return 'Syncing';
    return 'Connecting';
  })();

  const liveActive = liveTracking && catalogLive && (wsConnected || objectCount > 0);

  return (
    <div className="globe-hud">
      <div className="hud-chip">
        <Activity size={13} strokeWidth={1.75} />
        <span><strong>{objectCount.toLocaleString()}</strong> tracked</span>
      </div>
      <div className="hud-chip">
        <span className="hud-mono">{altitude}</span>
        <span className="hud-unit">km alt</span>
      </div>
      <div className={`hud-chip ${liveActive ? 'hud-chip--live' : ''}`}>
        {liveTracking ? <Wifi size={13} strokeWidth={1.75} /> : <Radio size={13} strokeWidth={1.75} />}
        <span>{liveLabel}</span>
      </div>
      <div className="hud-chip">
        {viewMode === 'heatmap' ? <Layers size={13} strokeWidth={1.75} /> : <Map size={13} strokeWidth={1.75} />}
        <span>{viewMode === 'heatmap' ? 'Heatmap' : 'Debris'}</span>
      </div>
    </div>
  );
}
