import { useState } from 'react';
import { Sparkles, Loader2 } from 'lucide-react';
import { aiPlanMission } from '../api';

const EXAMPLES = [
  'ISRO relay 650km',
  'EOS at 500km',
  'GSAT over India',
];

export default function AIMissionPlanner({ onPlanReady, onError, loading, setLoading }) {
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
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Describe your mission…"
          className="input-field flex-1"
        />
        <button
          type="submit"
          disabled={loading}
          className="btn-analyze"
          style={{ flex: 'none', padding: '9px 14px' }}
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
        </button>
      </form>
      <div className="flex gap-1.5 mt-2 flex-wrap">
        {EXAMPLES.map((ex) => (
          <button key={ex} type="button" onClick={() => setQuery(ex)} className="chip-btn">
            {ex}
          </button>
        ))}
      </div>
      {lastPlan?.plan && (
        <div className="ai-result">
          <p className="font-semibold text-cyan-400">{lastPlan.plan.mission_name}</p>
          <p className="text-slate-400 mt-1">{lastPlan.plan.rationale}</p>
          <p className="text-slate-500 mt-1">
            {lastPlan.plan.target_alt_km} km · Risk{' '}
            <span className={lastPlan.risk?.risk_score > 50 ? 'text-red-400' : 'text-green-400'}>
              {lastPlan.risk?.risk_score}/100
            </span>
          </p>
        </div>
      )}
    </div>
  );
}
