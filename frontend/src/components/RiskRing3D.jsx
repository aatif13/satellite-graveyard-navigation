export default function RiskRing3D({ score = 0 }) {
  const clamped = Math.min(100, Math.max(0, score));
  const color = clamped > 70 ? 'var(--danger)' : clamped > 40 ? 'var(--warning)' : 'var(--success)';
  const label = clamped > 70 ? 'High Risk' : clamped > 40 ? 'Moderate' : 'Low Risk';

  return (
    <div className="risk-gauge">
      <div
        className="risk-gauge-ring"
        style={{ '--pct': clamped, '--ring-color': color }}
      >
        <div className="risk-gauge-inner">
          <span className="risk-gauge-value" style={{ color }}>{clamped}</span>
          <span className="risk-gauge-label">{label}</span>
        </div>
      </div>
    </div>
  );
}
