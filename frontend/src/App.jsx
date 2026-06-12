import { useCallback, useEffect, useState } from 'react';
import {
  Satellite, Layers, Shield, RefreshCw, Trash2, Sparkles, TrendingDown,
} from 'lucide-react';
import SpaceGlobe from './components/SpaceGlobe';
import AIMissionPlanner from './components/AIMissionPlanner';
import ReportButton from './components/ReportGenerator';
import MissionPresets from './components/MissionPresets';
import GlobeHUD from './components/GlobeHUD';
import RiskRing3D from './components/RiskRing3D';
import Section from './components/Section';
import { useLiveDebris } from './hooks/useLiveDebris';
import {
  fetchDebris, fetchHeatmap, fetchIsroConstellation, analyzeOrbit, fetchPresets,
} from './api';

export default function App() {
  const [debris, setDebris] = useState([]);
  const [heatmap, setHeatmap] = useState([]);
  const [presets, setPresets] = useState([]);
  const [waypoints, setWaypoints] = useState([]);
  const [selectedAlt, setSelectedAlt] = useState(550);
  const [analysis, setAnalysis] = useState(null);
  const [isroOnly, setIsroOnly] = useState(false);
  const [viewMode, setViewMode] = useState('points');
  const [liveTracking, setLiveTracking] = useState(true);
  const [catalogSyncing, setCatalogSyncing] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [findingSafe, setFindingSafe] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [isroData, setIsroData] = useState(null);
  const [missionName, setMissionName] = useState('Proposed LEO Mission');
  const [activePresetId, setActivePresetId] = useState(null);
  const [orbitSafeApplied, setOrbitSafeApplied] = useState(false);
  const [error, setError] = useState(null);
  const [prevRiskScore, setPrevRiskScore] = useState(null);
  const [catalogLive, setCatalogLive] = useState(false);
  const [catalogSource, setCatalogSource] = useState('cache');

  const refreshHeatmap = useCallback(() => {
    fetchHeatmap().then((d) => setHeatmap(d.points)).catch(() => {});
  }, []);

  const handleWsUpdate = useCallback(({ objects, refreshing, catalog_live: live, catalog_source: source }) => {
    if (refreshing) {
      setCatalogSyncing(true);
      return;
    }
    setDebris(objects);
    if (live != null) setCatalogLive(live);
    if (source) setCatalogSource(source);
    if (objects?.length > 0) setCatalogSyncing(false);
    refreshHeatmap();
  }, [refreshHeatmap]);

  const { connected: wsConnected, refresh: wsRefresh } = useLiveDebris({
    enabled: liveTracking,
    isroOnly,
    onUpdate: handleWsUpdate,
  });

  const loadDebrisHttp = useCallback(async (refresh = false) => {
    try {
      setError(null);
      const data = await fetchDebris({ isroOnly, refresh });
      setDebris(data.objects);
      setCatalogLive(Boolean(data.catalog_live));
      if (data.catalog_source) setCatalogSource(data.catalog_source);
      if (data.objects?.length > 0 && !refresh) setCatalogSyncing(false);
      refreshHeatmap();
    } catch (err) {
      setError(err.message);
    } finally {
      if (!refresh) setCatalogSyncing(false);
    }
  }, [isroOnly, refreshHeatmap]);

  useEffect(() => {
    if (!liveTracking) loadDebrisHttp();
  }, [liveTracking, loadDebrisHttp]);

  useEffect(() => {
    if (!liveTracking) return undefined;
    const fallback = setTimeout(() => {
      if (debris.length === 0) loadDebrisHttp();
    }, 1500);
    return () => clearTimeout(fallback);
  }, [liveTracking, debris.length, loadDebrisHttp]);

  useEffect(() => {
    fetchIsroConstellation().then(setIsroData).catch((e) => setError(e.message));
    fetchHeatmap().then((d) => setHeatmap(d.points)).catch(() => {});
    fetchPresets().then((d) => setPresets(d.presets)).catch((e) => setError(e.message));
    fetch('/api/health').then((r) => r.json()).then((h) => {
      setCatalogLive(Boolean(h.catalog_live));
      if (h.catalog_source) setCatalogSource(h.catalog_source);
    }).catch(() => {});
  }, []);

  const syncWaypointsAlt = (alt) =>
    waypoints.map((wp) => ({ ...wp, alt_km: alt }));

  const debrisForAnalysis = useCallback(() => {
    if (!debris.length) return null;
    return debris
      .filter((d) => {
        const a = d.alt_km ?? d.alt ?? 0;
        return a >= 150 && a <= 2500;
      })
      .map((d) => ({
        name: d.name,
        lat: d.lat,
        lng: d.lng,
        alt: d.alt_km ?? d.alt,
        alt_km: d.alt_km ?? d.alt,
        vx: d.vx ?? 0,
        vy: d.vy ?? 0,
        vz: d.vz ?? 0,
        is_isro: d.is_isro,
      }));
  }, [debris]);

  const runAnalysis = useCallback(async (wps, alt) => {
    const catalog = debrisForAnalysis();
    const result = await analyzeOrbit(
      wps,
      alt,
      catalog?.length >= 50 ? catalog : null,
    );
    setAnalysis(result);
    setError(null);
    return result;
  }, [debrisForAnalysis]);

  const handleOrbitClick = ({ lat, lng }) => {
    setWaypoints((prev) => [...prev, { lat, lng, alt_km: selectedAlt }]);
    setAnalysis(null);
    setOrbitSafeApplied(false);
    setActivePresetId(null);
  };

  const handleAnalyze = async () => {
    if (waypoints.length < 2) return;
    setAnalyzing(true);
    setOrbitSafeApplied(false);
    setPrevRiskScore(null);
    const synced = syncWaypointsAlt(selectedAlt);
    setWaypoints(synced);
    try {
      const result = await runAnalysis(synced, selectedAlt);
      if (!result) return;
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleFindSaferAltitude = async () => {
    if (!analysis?.safe_altitude || waypoints.length < 2) return;
    const safeAlt = analysis.safe_altitude;
    setPrevRiskScore(analysis.risk_score);
    setFindingSafe(true);
    const newWaypoints = waypoints.map((wp) => ({ ...wp, alt_km: safeAlt }));
    setSelectedAlt(safeAlt);
    setWaypoints(newWaypoints);
    setMissionName(`${missionName.split(' → ')[0]} → Safer @ ${safeAlt}km`);
    try {
      await runAnalysis(newWaypoints, safeAlt);
      setOrbitSafeApplied(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setFindingSafe(false);
    }
  };

  const handlePresetSelect = async (preset) => {
    setActivePresetId(preset.id);
    setWaypoints(preset.waypoints);
    setSelectedAlt(preset.alt_km);
    setMissionName(preset.name);
    setOrbitSafeApplied(false);
    setAnalysis(null);
    setAnalyzing(true);
    try {
      await runAnalysis(preset.waypoints, preset.alt_km);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleAiPlan = async (result) => {
    const rawAlt = result.plan.target_alt_km || 550;
    const orbitType = (result.plan.orbit_type || 'LEO').toUpperCase();
    const isLeo = orbitType === 'LEO' || (orbitType !== 'GEO' && orbitType !== 'MEO');
    const alt = orbitType === 'GEO'
      ? 35786
      : orbitType === 'MEO'
        ? Math.min(20000, Math.max(2000, rawAlt))
        : Math.min(2000, Math.max(200, rawAlt));
    const wps = (result.plan.suggested_waypoints || []).map((wp) => ({ ...wp, alt_km: alt }));
    setWaypoints(wps);
    setSelectedAlt(isLeo ? alt : Math.min(2000, alt));
    setMissionName(result.plan.mission_name || 'AI Planned Mission');
    setActivePresetId(null);
    setOrbitSafeApplied(false);
    setAnalyzing(true);
    try {
      await runAnalysis(wps, alt);
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleClear = () => {
    setWaypoints([]);
    setAnalysis(null);
    setOrbitSafeApplied(false);
    setActivePresetId(null);
    setPrevRiskScore(null);
    setSelectedAlt(550);
    setMissionName('Proposed LEO Mission');
    setError(null);
  };

  useEffect(() => {
    if (waypoints.length < 2 || analyzing || debris.length < 50) return;
    const missionAlt = waypoints[0]?.alt_km ?? selectedAlt;
    const needsRefresh = !analysis || analysis.data_ready === false || analysis.catalog_size < debris.length * 0.5;
    if (!needsRefresh) return;
    runAnalysis(waypoints, missionAlt).catch(() => {});
  }, [debris.length, catalogLive]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleAltChange = (alt) => {
    setSelectedAlt(alt);
    setOrbitSafeApplied(false);
    if (waypoints.length > 0) {
      setWaypoints((prev) => prev.map((wp) => ({ ...wp, alt_km: alt })));
    }
  };

  const score = analysis?.risk_score ?? 0;
  const riskDelta = prevRiskScore != null && analysis ? prevRiskScore - score : null;

  return (
    <div className="app-shell">
      <div className="globe-area">
        <SpaceGlobe
          debrisData={debris}
          waypoints={waypoints}
          dangerZones={analysis?.danger_zones}
          viewMode={viewMode}
          heatmapData={heatmap}
          onOrbitClick={handleOrbitClick}
          orbitSafeApplied={orbitSafeApplied}
        />

        {catalogSyncing && (
          <div className="loading-badge">
            <div className="loading-spinner" />
            <span>
              {debris.length === 0
                ? (wsConnected ? 'Syncing orbital catalog…' : 'Connecting to mission control…')
                : 'Refreshing TLE catalog…'}
            </span>
          </div>
        )}

        <div className="globe-title-3d">
          <h1><Satellite size={18} /> Graveyard Navigator</h1>
          <p>
            FAR AWAY 2026 ·{' '}
            {catalogLive
              ? (catalogSource === 'space-track' ? 'SPACE-TRACK' : 'CELESTRAK')
              : 'DEMO'}{' '}
            · SGP4
          </p>
        </div>

        <GlobeHUD
          objectCount={debris.length}
          wsConnected={wsConnected}
          liveTracking={liveTracking}
          catalogLive={catalogLive}
          altitude={waypoints[0]?.alt_km ?? selectedAlt}
          viewMode={viewMode}
        />
      </div>

      <aside className="cockpit-panel">
        <div className="cockpit-header">
          <h2>Mission Control</h2>
          <p className="mission-tag">{missionName}</p>
        </div>

        <div className="cockpit-scroll">
          {error && <div className="error-banner">{error}</div>}

          <Section title="Quick Presets" icon={Satellite}>
            <MissionPresets presets={presets} activeId={activePresetId} onSelect={handlePresetSelect} />
          </Section>

          <Section title="AI Planner" icon={Sparkles}>
            <AIMissionPlanner
              onPlanReady={handleAiPlan}
              onError={setError}
              loading={aiLoading}
              setLoading={setAiLoading}
            />
          </Section>

          <Section title="Draw Orbit" icon={Shield}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-500">Altitude</span>
              <span className="text-cyan-400 font-mono font-semibold">{selectedAlt} km</span>
            </div>
            <input
              type="range"
              min={200}
              max={2000}
              step={10}
              value={selectedAlt}
              onChange={(e) => handleAltChange(Number(e.target.value))}
              className="alt-slider"
            />
            <p className="text-[11px] text-slate-600 mb-3">
              Click globe to place waypoints · <span className="text-slate-400">{waypoints.length} set</span>
            </p>
            <div className="flex gap-2">
              <button type="button" onClick={handleAnalyze} disabled={waypoints.length < 2 || analyzing} className="btn-analyze">
                <Shield size={14} />
                {analyzing ? 'Analyzing…' : 'Analyze Risk'}
              </button>
              <button type="button" onClick={handleClear} className="btn-icon" title="Clear orbit">
                <Trash2 size={14} />
              </button>
            </div>
          </Section>

          {analysis && (
            <Section title="Risk Analysis" accent>
              <RiskRing3D score={score} />

              {riskDelta != null && riskDelta !== 0 && (
                <p className="risk-delta" style={{ color: riskDelta > 0 ? '#4ade80' : '#f87171' }}>
                  {riskDelta > 0 ? `↓ ${riskDelta} pts safer` : `↑ ${Math.abs(riskDelta)} pts riskier`}
                </p>
              )}

              {analysis.warning && (
                <p className="text-center text-[11px] text-amber-400 mb-2">{analysis.warning}</p>
              )}

              <p className="text-center text-[11px] text-slate-500 mt-2 mb-3">
                {analysis.nearby_count} objects in band
                {analysis.catalog_size != null && ` · ${analysis.catalog_size.toLocaleString()} tracked`}
              </p>

              <div className="stat-grid mb-3">
                {[
                  { label: 'Density', val: analysis.risk_breakdown?.density, color: '#06b6d4' },
                  { label: 'Crossing', val: analysis.risk_breakdown?.velocity_crossing, color: '#f59e0b' },
                  { label: 'Overlap', val: analysis.risk_breakdown?.altitude_overlap, color: '#ef4444' },
                ].map(({ label, val, color }) => (
                  <div key={label} className="stat-3d">
                    <label>{label}</label>
                    <span style={{ color }}>{val ?? 0} pts</span>
                  </div>
                ))}
              </div>

              <button
                type="button"
                onClick={handleFindSaferAltitude}
                disabled={findingSafe || !analysis.safe_altitude || (orbitSafeApplied && Math.abs(analysis.safe_altitude - selectedAlt) < 50)}
                className="btn-safe"
              >
                <TrendingDown size={14} />
                {findingSafe ? 'Re-scoring…' : orbitSafeApplied ? `Applied @ ${selectedAlt} km` : `Safer Altitude → ${analysis.safe_altitude} km`}
              </button>

              {analysis.launch_windows?.length > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-800">
                  <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-2">Launch Windows</p>
                  {analysis.launch_windows.slice(0, 3).map((w) => (
                    <div key={`${w.date}-${w.utc_hour}`} className="launch-row">
                      <span>{w.date} {String(w.utc_hour).padStart(2, '0')}:00</span>
                      <span className={w.risk_pct < 35 ? 'text-green-400' : 'text-amber-400'}>{w.label}</span>
                    </div>
                  ))}
                </div>
              )}
            </Section>
          )}

          <Section title="Display" icon={Layers}>
            <Toggle label="Live Tracking" sub="WebSocket push" checked={liveTracking} onChange={setLiveTracking} />
            <Toggle label="ISRO View" sub={`${isroData?.tracked_isro_count ?? '—'} assets`} checked={isroOnly} onChange={setIsroOnly} orange />
            <Toggle label="Heatmap" sub="Shell congestion" checked={viewMode === 'heatmap'} onChange={(v) => setViewMode(v ? 'heatmap' : 'points')} />
          </Section>
        </div>

        <div className="cockpit-footer">
          <ReportButton waypoints={waypoints} analysis={analysis} missionName={missionName} isroMissions={isroData?.missions} />
          <button
            type="button"
            onClick={() => {
              setCatalogSyncing(true);
              if (liveTracking) wsRefresh();
              else loadDebrisHttp(true);
            }}
            className="flex items-center justify-center gap-1.5 w-full mt-2 text-[11px] text-slate-600 hover:text-cyan-400 transition-colors py-1"
          >
            <RefreshCw size={11} /> Refresh TLE data
          </button>
        </div>
      </aside>
    </div>
  );
}

function Toggle({ label, sub, checked, onChange, orange = false }) {
  return (
    <div className="toggle-3d" onClick={() => onChange(!checked)} role="switch" aria-checked={checked}>
      <div>
        <label>{label}</label>
        <small>{sub}</small>
      </div>
      <div className={`toggle-pill ${checked ? 'on' : ''} ${orange ? 'orange' : ''}`} />
    </div>
  );
}
