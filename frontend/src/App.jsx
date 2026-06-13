import { useCallback, useState } from 'react';
import Landing from './components/Landing';
import MissionControl from './MissionControl';

export default function App() {
  const [view, setView] = useState('landing');
  const [entering, setEntering] = useState(false);

  const enterMissionControl = useCallback(() => {
    setEntering(true);
    window.setTimeout(() => {
      setView('app');
      setEntering(false);
    }, 420);
  }, []);

  const returnHome = useCallback(() => {
    setView('landing');
  }, []);

  if (view === 'app') {
    return <MissionControl onHome={returnHome} />;
  }

  return <Landing onEnter={enterMissionControl} entering={entering} />;
}
