function riskLabel(score) {
  if (score > 70) return 'High Risk';
  if (score > 40) return 'Moderate';
  return 'Low Risk';
}

function riskClass(score) {
  if (score > 70) return 'risk-compare__value--high';
  if (score > 40) return 'risk-compare__value--mid';
  return 'risk-compare__value--low';
}

export default function RiskCompare({ before, after, beforeLabel = 'Before', afterLabel = 'After' }) {
  if (before == null && after == null) return null;

  const showDelta = before != null && after != null && before !== after;
  const delta = showDelta ? before - after : 0;

  return (
    <div className="risk-compare">
      <div className="risk-compare__col">
        <span className="risk-compare__label">{beforeLabel}</span>
        <span className={`risk-compare__value ${riskClass(before ?? after)}`}>
          {before ?? '—'}
        </span>
        <span className="risk-compare__sublabel">{riskLabel(before ?? after)}</span>
      </div>
      <div className="risk-compare__divider">
        {showDelta && (
          <span className={`risk-compare__delta ${delta > 0 ? 'risk-compare__delta--good' : 'risk-compare__delta--bad'}`}>
            {delta > 0 ? `↓ ${delta}` : `↑ ${Math.abs(delta)}`}
          </span>
        )}
      </div>
      <div className="risk-compare__col">
        <span className="risk-compare__label">{afterLabel}</span>
        <span className={`risk-compare__value ${riskClass(after ?? before)}`}>
          {after ?? '—'}
        </span>
        <span className="risk-compare__sublabel">{riskLabel(after ?? before)}</span>
      </div>
    </div>
  );
}
