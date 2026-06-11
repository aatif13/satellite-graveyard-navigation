import { useEffect, useRef } from 'react';
import Globe from 'globe.gl';

const EARTH_IMG = `${import.meta.env.BASE_URL}textures/earth-night.jpg`;
const SKY_IMG = `${import.meta.env.BASE_URL}textures/night-sky.png`;

function preloadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(url);
    img.onerror = () => reject(new Error(`Failed to load ${url}`));
    img.src = url;
  });
}

export default function SpaceGlobe({
  debrisData,
  waypoints,
  dangerZones,
  viewMode,
  heatmapData,
  onOrbitClick,
  orbitSafeApplied = false,
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
      try {
        await Promise.all([preloadImage(EARTH_IMG), preloadImage(SKY_IMG)]);
      } catch {
        /* globe still renders with fallback material */
      }
      if (cancelled) return;

      const w = mount.clientWidth || 800;
      const h = mount.clientHeight || 600;

      globe = Globe()(mount)
        .globeImageUrl(EARTH_IMG)
        .backgroundImageUrl(SKY_IMG)
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
        const nw = mount.clientWidth;
        const nh = mount.clientHeight;
        if (nw > 0 && nh > 0) {
          globeRef.current.width(nw).height(nh);
        }
      };

      window.addEventListener('resize', handleResize);
      ro = new ResizeObserver(handleResize);
      ro.observe(mount);

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

    if (viewMode === 'heatmap') {
      if (!heatmapData?.length) {
        globe.pointsData([]).arcsData([]).ringsData([]);
        return;
      }
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
        })
        .ringsData([])
        .arcsData([]);
    } else {
      globe
        .pointsData(debrisData || [])
        .pointLat((d) => d.lat)
        .pointLng((d) => d.lng)
        .pointAltitude((d) => Math.max(0.002, (d.alt_km ?? d.alt ?? 400) / 6371))
        .pointRadius(0.14)
        .pointColor((d) => {
          if (d.is_isro) return '#fb923c';
          const alt = d.alt_km ?? d.alt ?? 0;
          if (alt < 600) return '#f87171';
          if (alt < 1200) return '#fbbf24';
          return '#22d3ee';
        });
    }

    const arcs = [];
    if (waypoints?.length >= 2) {
      for (let i = 0; i < waypoints.length - 1; i++) {
        arcs.push({
          startLat: waypoints[i].lat,
          startLng: waypoints[i].lng,
          endLat: waypoints[i + 1].lat,
          endLng: waypoints[i + 1].lng,
          alt: (waypoints[i].alt_km || 500) / 6371,
        });
      }
      const last = waypoints[waypoints.length - 1];
      const first = waypoints[0];
      arcs.push({
        startLat: last.lat,
        startLng: last.lng,
        endLat: first.lat,
        endLng: first.lng,
        alt: (last.alt_km || 500) / 6371,
      });
    }

    const arcColor = orbitSafeApplied ? '#4ade80' : '#fbbf24';
    globe
      .arcsData(arcs)
      .arcColor(() => arcColor)
      .arcAltitude((d) => d.alt || 0.1)
      .arcStroke(orbitSafeApplied ? 0.9 : 0.55)
      .arcDashLength(orbitSafeApplied ? 0.35 : 1)
      .arcDashGap(orbitSafeApplied ? 0.12 : 0)
      .arcDashAnimateTime(orbitSafeApplied ? 1800 : 0)
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
  }, [debrisData, waypoints, dangerZones, viewMode, heatmapData, orbitSafeApplied]);

  return (
    <div className="globe-canvas-host">
      <div ref={mountRef} className="globe-mount" />
    </div>
  );
}
