import { useEffect, useRef } from 'react';
import Globe from 'globe.gl';

const LOCAL_EARTH = `${import.meta.env.BASE_URL}textures/earth-night.jpg`;
const LOCAL_SKY = `${import.meta.env.BASE_URL}textures/night-sky.png`;
const CDN_EARTH = 'https://unpkg.com/three-globe/example/img/earth-night.jpg';
const CDN_SKY = 'https://unpkg.com/three-globe/example/img/night-sky.png';

async function resolveTexture(localUrl, cdnUrl) {
  try {
    await preloadImage(localUrl);
    return localUrl;
  } catch {
    await preloadImage(cdnUrl);
    return cdnUrl;
  }
}

function preloadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(url);
    img.onerror = () => reject(new Error(`Failed to load ${url}`));
    img.src = url;
  });
}

function estimateLocalRisk(lat, lng, altKm, debris) {
  if (!debris?.length) return 0;
  let nearby = 0;
  const altTol = 80;
  for (const d of debris) {
    const dAlt = d.alt_km ?? d.alt ?? 0;
    if (Math.abs(dAlt - altKm) > altTol) continue;
    const dLat = d.lat ?? 0;
    const dLng = d.lng ?? 0;
    const dist = Math.hypot(lat - dLat, lng - dLng);
    if (dist < 8) nearby += 1;
  }
  return Math.min(1, nearby / 15);
}

function riskToColor(t, safeApplied) {
  if (safeApplied) return '#34c759';
  if (t > 0.66) return '#ef4444';
  if (t > 0.33) return '#f59e0b';
  return '#34c759';
}

function buildSegmentedOrbitPaths(inclinationDeg, altKm, debris, orbitSafeApplied, segments = 8, pointsPerSeg = 12) {
  const inc = (inclinationDeg * Math.PI) / 180;
  const alt = altKm / 6371;
  const paths = [];
  const totalPoints = segments * pointsPerSeg;

  for (let s = 0; s < segments; s += 1) {
    const coords = [];
    for (let i = 0; i <= pointsPerSeg; i += 1) {
      const idx = s * pointsPerSeg + i;
      const nu = (idx / totalPoints) * 2 * Math.PI;
      const lat = Math.asin(Math.max(-1, Math.min(1, Math.sin(inc) * Math.sin(nu)))) * (180 / Math.PI);
      const lng = Math.atan2(Math.cos(inc) * Math.sin(nu), Math.cos(nu)) * (180 / Math.PI);
      coords.push({ lat, lng, alt });
    }
    const mid = coords[Math.floor(coords.length / 2)];
    const localRisk = estimateLocalRisk(mid.lat, mid.lng, altKm, debris);
    paths.push({
      coords,
      color: riskToColor(localRisk, orbitSafeApplied),
    });
  }
  return paths;
}

export default function SpaceGlobe({
  debrisData,
  waypoints,
  dangerZones,
  viewMode,
  heatmapData,
  onOrbitClick,
  orbitSafeApplied = false,
  criticalObjects = [],
}) {
  const mountRef = useRef(null);
  const globeRef = useRef(null);
  const onOrbitClickRef = useRef(onOrbitClick);
  onOrbitClickRef.current = onOrbitClick;

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    let globe = null;
    let ro = null;
    let cancelled = false;

    const init = async () => {
      let earthImg = CDN_EARTH;
      let skyImg = CDN_SKY;
      try {
        [earthImg, skyImg] = await Promise.all([
          resolveTexture(LOCAL_EARTH, CDN_EARTH),
          resolveTexture(LOCAL_SKY, CDN_SKY),
        ]);
      } catch {
        /* globe still renders with fallback material */
      }
      if (cancelled) return;

      const host = mount.parentElement;
      const w = host?.clientWidth || mount.clientWidth || 800;
      const h = host?.clientHeight || mount.clientHeight || 600;

      globe = Globe()(mount)
        .globeImageUrl(earthImg)
        .backgroundImageUrl(skyImg)
        .showAtmosphere(true)
        .atmosphereColor('#22d3ee')
        .atmosphereAltitude(0.18)
        .width(w)
        .height(h);

      globe.controls().autoRotate = true;
      globe.controls().autoRotateSpeed = 0.35;
      globe.pointOfView({ lat: 22, lng: 78, altitude: 2.4 });

      globe.onGlobeClick(({ lat, lng }) => {
        onOrbitClickRef.current?.({ lat, lng });
      });

      globeRef.current = globe;

      const handleResize = () => {
        if (!mount || !globeRef.current) return;
        const container = mount.parentElement || mount;
        const nw = container.clientWidth;
        const nh = container.clientHeight;
        if (nw > 0 && nh > 0) {
          globeRef.current.width(nw).height(nh);
        }
      };

      window.addEventListener('resize', handleResize);
      ro = new ResizeObserver(handleResize);
      ro.observe(mount.parentElement || mount);

      mount._cleanupResize = () => {
        window.removeEventListener('resize', handleResize);
        ro?.disconnect();
      };
    };

    requestAnimationFrame(() => requestAnimationFrame(init));

    return () => {
      cancelled = true;
      mount._cleanupResize?.();
      if (globe?._destructor) globe._destructor();
      mount.innerHTML = '';
      globeRef.current = null;
    };
  }, []);

  useEffect(() => {
    const globe = globeRef.current;
    if (!globe) return;

    if (viewMode === 'heatmap' && heatmapData?.length) {
      globe
        .pointsData(heatmapData)
        .pointLat((d) => d.lat)
        .pointLng((d) => d.lng)
        .pointAltitude((d) => (d.alt_km || 400) / 6371)
        .pointRadius((d) => 0.35 + d.weight * 1.4)
        .pointColor((d) => {
          if (d.weight > 0.7) return '#ef4444';
          if (d.weight > 0.4) return '#f59e0b';
          return '#06b6d4';
        });
    } else if (viewMode === 'heatmap') {
      globe.pointsData([]);
    } else {
      globe
        .pointsData(debrisData || [])
        .pointLat((d) => d.lat)
        .pointLng((d) => d.lng)
        .pointAltitude((d) => Math.max(0.004, (d.alt_km ?? d.alt ?? 400) / 6371))
        .pointRadius(0.06)
        .pointColor((d) => {
          if (d.is_isro) return '#fb923c';
          const alt = d.alt_km ?? d.alt ?? 0;
          if (alt < 600) return '#f87171';
          if (alt < 1200) return '#fbbf24';
          return '#22d3ee';
        });
    }

    const altKm = waypoints?.[0]?.alt_km ?? 500;
    const maxAbsLat = waypoints?.length >= 2
      ? Math.max(...waypoints.map((w) => Math.abs(w.lat)))
      : 0;
    const orbitPaths = waypoints?.length >= 2
      ? buildSegmentedOrbitPaths(maxAbsLat || 51.6, altKm, debrisData, orbitSafeApplied)
      : [];

    const labelItems = (criticalObjects || [])
      .slice(0, 5)
      .filter((o) => o.lat != null && o.lng != null)
      .map((o) => ({
        lat: o.lat,
        lng: o.lng,
        text: `${o.name} · NORAD ${o.norad_id ?? '—'}`,
        alt: (o.alt_km ?? altKm) / 6371,
      }));

    globe
      .arcsData([])
      .pathsData(orbitPaths)
      .pathPoints('coords')
      .pathPointLat((p) => p.lat)
      .pathPointLng((p) => p.lng)
      .pathPointAlt((p) => p.alt)
      .pathColor((path) => path.color)
      .pathStroke(orbitSafeApplied ? 1.2 : 0.9)
      .pathDashLength(orbitSafeApplied ? 0.4 : 1)
      .pathDashGap(orbitSafeApplied ? 0.15 : 0)
      .pathDashAnimateTime(orbitSafeApplied ? 2000 : 0)
      .labelsData(labelItems)
      .labelLat((d) => d.lat)
      .labelLng((d) => d.lng)
      .labelAltitude((d) => d.alt)
      .labelText((d) => d.text)
      .labelSize(1.2)
      .labelColor(() => '#fca5a5')
      .labelDotRadius(0.4)
      .labelDotOrientation(() => 'top')
      .labelResolution(2)
      .ringsData(
        viewMode === 'heatmap' ? [] : (dangerZones || []).map((z) => ({
          lat: z.lat,
          lng: z.lng,
          maxR: 3 + z.count * 0.35,
        }))
      )
      .ringColor((t) => `rgba(248,113,113,${1 - t})`)
      .ringMaxRadius('maxR')
      .ringPropagationSpeed(2.5)
      .ringRepeatPeriod(1100);
  }, [debrisData, waypoints, dangerZones, viewMode, heatmapData, orbitSafeApplied, criticalObjects]);

  return (
    <div className="globe-canvas-host">
      <div ref={mountRef} className="globe-mount" />
    </div>
  );
}
