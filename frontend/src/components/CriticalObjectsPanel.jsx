export default function CriticalObjectsPanel({ objects }) {
  const top = (objects || []).slice(0, 5);
  if (!top.length) return null;

  return (
    <div className="critical-panel">
      <p className="critical-panel__title">Top conjunction threats</p>
      <ul className="critical-panel__list">
        {top.map((obj) => (
          <li key={`${obj.name}-${obj.norad_id}`}>
            <span className="critical-panel__name">{obj.name}</span>
            <span className="critical-panel__meta">
              {obj.norad_id ? `NORAD ${obj.norad_id}` : 'NORAD —'}
              {' · '}
              {obj.alt_km} km
              {' · '}
              ×{obj.crossing_factor}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
