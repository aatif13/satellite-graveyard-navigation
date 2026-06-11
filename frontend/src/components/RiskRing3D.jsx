export default function RiskRing3D({ score = 0 }) {
  const clamped = Math.min(100, Math.max(0, score));
  const color = clamped > 70 ? '#ef4444' : clamped > 40 ? '#f59e0b' : '#22c55e';
  const label = clamped > 70 ? 'DANGER' : clamped > 40 ? 'CAUTION' : 'SAFE';

  return (
    <div className="risk-ring-3d">
      <div className="risk-ring-disc" style={{ '--pct': clamped, '--ring-color': color }}>
        <div className="risk-ring-inner">
          <span className="risk-ring-value" style={{ color }}>{clamped}</span>
          <span className="risk-ring-label">{label}</span>
        </div>
      </div>
    </div>
  );
}
