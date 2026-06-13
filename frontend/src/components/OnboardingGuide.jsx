import { useEffect, useState } from 'react';
import { X } from 'lucide-react';

const STORAGE_KEY = 'sgn-onboarding-done';

const STEPS = [
  { n: 1, text: 'Click globe → place orbit waypoints' },
  { n: 2, text: 'Analyze → score conjunction risk' },
  { n: 3, text: 'Safer Altitude → find a cleaner band' },
];

export default function OnboardingGuide() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY) === '1') return undefined;
    setVisible(true);
    const timer = window.setTimeout(() => {
      setVisible(false);
      localStorage.setItem(STORAGE_KEY, '1');
    }, 30000);
    return () => clearTimeout(timer);
  }, []);

  const dismiss = () => {
    setVisible(false);
    localStorage.setItem(STORAGE_KEY, '1');
  };

  if (!visible) return null;

  return (
    <div className="onboarding-guide">
      <div className="onboarding-guide__head">
        <strong>Quick start</strong>
        <button type="button" className="onboarding-guide__close" onClick={dismiss} aria-label="Dismiss">
          <X size={14} />
        </button>
      </div>
      <ol className="onboarding-guide__steps">
        {STEPS.map(({ n, text }) => (
          <li key={n}>
            <span className="onboarding-guide__num">{n}</span>
            {text}
          </li>
        ))}
      </ol>
    </div>
  );
}
