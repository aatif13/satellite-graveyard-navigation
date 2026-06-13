import { Activity, Layers, Map, Radio, Wifi } from 'lucide-react';

export default function GlobeHUD({ objectCount, wsConnected, liveTracking, catalogLive, altitude, viewMode }) {
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
      <div className={`hud-chip ${liveTracking && wsConnected && catalogLive ? 'hud-chip--live' : ''}`}>
        {liveTracking ? <Wifi size={13} strokeWidth={1.75} /> : <Radio size={13} strokeWidth={1.75} />}
        <span>
          {liveTracking
            ? (catalogLive && wsConnected ? 'Live' : wsConnected ? 'Syncing' : 'Connecting')
            : 'Paused'}
        </span>
      </div>
      <div className="hud-chip">
        {viewMode === 'heatmap' ? <Layers size={13} strokeWidth={1.75} /> : <Map size={13} strokeWidth={1.75} />}
        <span>{viewMode === 'heatmap' ? 'Heatmap' : 'Debris'}</span>
      </div>
    </div>
  );
}
