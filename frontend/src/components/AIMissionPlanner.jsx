import { useState } from 'react';
import { Sparkles, Loader2 } from 'lucide-react';
import { aiPlanMission } from '../api';

const EXAMPLES = [
  'ISRO relay 650km',
  'EOS at 500km',
  'GSAT over India',
];

export default function AIMissionPlanner({ onPlanReady, onError, loading, setLoading, riskScore }) {
  const [query, setQuery] = useState('');
  const [lastPlan, setLastPlan] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    try {
      const result = await aiPlanMission(query);
      setLastPlan(result);
      onPlanReady?.(result);
    } catch (err) {
      onError?.(err.message || 'AI planning failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit} className="btn-row">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Describe your mission…"
          className="input-field"
          style={{ flex: 1 }}
        />
        <button
          type="submit"
          disabled={loading}
          className="btn-primary btn-primary--icon"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
        </button>
      </form>
      <div className="chip-row">
        {EXAMPLES.map((ex) => (
          <button key={ex} type="button" onClick={() => setQuery(ex)} className="chip-btn">
            {ex}
          </button>
        ))}
      </div>
      {lastPlan?.plan && (
        <div className="ai-result">
          <p className="ai-result-title">{lastPlan.plan.mission_name}</p>
          <p className="ai-result-body">{lastPlan.plan.rationale}</p>
          <p className="ai-result-meta">
            {lastPlan.plan.target_alt_km} km
            {riskScore != null && (
              <>
                {' · Risk '}
                <span className={riskScore > 50 ? 'text-danger' : 'text-success'}>
                  {riskScore}/100
                </span>
              </>
            )}
          </p>
        </div>
      )}
    </div>
  );
}
