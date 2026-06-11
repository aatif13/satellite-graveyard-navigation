import { Activity, Radio, Wifi } from 'lucide-react';

export default function GlobeHUD({ objectCount, wsConnected, liveTracking, altitude, viewMode }) {
  return (
    <div className="globe-hud-3d">
      <div className="hud-3d-chip">
        <Activity size={13} className="text-cyan-400" />
        <span><strong>{objectCount.toLocaleString()}</strong> objects</span>
      </div>
      <div className="hud-3d-chip">
        <span className="text-cyan-300 font-mono">{altitude}</span>
        <span className="text-slate-500">km</span>
      </div>
      <div className={`hud-3d-chip ${liveTracking && wsConnected ? 'hud-live' : ''}`}>
        {liveTracking ? <Wifi size={13} /> : <Radio size={13} />}
        {liveTracking ? (wsConnected ? 'LIVE' : 'SYNC…') : 'PAUSED'}
      </div>
      <div className="hud-3d-chip">
        {viewMode === 'heatmap' ? '🔥 Heatmap' : '◎ Debris'}
      </div>
    </div>
  );
}
