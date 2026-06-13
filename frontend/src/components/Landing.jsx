import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Globe2, Radar, Shield, Sparkles, Satellite } from 'lucide-react';

const HERO_VIDEO =
  'https://res.cloudinary.com/dfonotyfb/video/upload/q_auto,f_mp4/v1775585556/dds3_1_rqhg7x.mp4';
const HERO_POSTER =
  'https://res.cloudinary.com/dfonotyfb/video/upload/so_0,q_auto,f_jpg/v1775585556/dds3_1_rqhg7x.jpg';

const FEATURES = [
  { icon: Globe2, title: '3D Debris Globe', desc: 'Live SGP4 propagation across a full orbital catalog.' },
  { icon: Shield, title: 'Velocity-Aware Risk', desc: 'Quantified collision scoring with density and crossing analysis.' },
  { icon: Sparkles, title: 'AI Mission Planner', desc: 'Natural-language orbit planning with instant risk feedback.' },
  { icon: Radar, title: 'ISRO Constellation', desc: 'Dedicated filtering for Indian space assets and missions.' },
];

export default function Landing({ onEnter, entering = false }) {
  const videoRef = useRef(null);
  const [videoReady, setVideoReady] = useState(false);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return undefined;
    const tryPlay = () => {
      video.play().then(() => setVideoReady(true)).catch(() => setVideoReady(true));
    };
    tryPlay();
    video.addEventListener('loadeddata', tryPlay);
    return () => video.removeEventListener('loadeddata', tryPlay);
  }, []);

  return (
    <section className={`landing ${videoReady ? 'landing--video-on' : ''} ${entering ? 'landing--exit' : ''}`}>
      <div className="landing-media" style={{ backgroundImage: `url(${HERO_POSTER})` }}>
        <video ref={videoRef} autoPlay loop muted playsInline preload="auto" poster={HERO_POSTER} className="landing-video" aria-hidden>
          <source src={HERO_VIDEO} type="video/mp4" />
        </video>
        <div className="landing-overlay" aria-hidden />
      </div>

      <header className="landing-top">
        <div className="landing-logo">
          <Satellite size={18} strokeWidth={1.75} />
          <div>
            <strong>Graveyard Navigator</strong>
            <span>Orbital debris intelligence</span>
          </div>
        </div>
        <span className="landing-tag">FAR AWAY 2026</span>
      </header>

      <main className="landing-main">
        <div className="landing-hero-copy">
          <p className="landing-kicker">Space & Aerospace · Live TLE · SGP4</p>
          <h1>
            Navigate the orbital
            <em> graveyard</em>
          </h1>
          <p className="landing-lead">
            Plan safer missions against real debris data. Analyze collision risk on a live 3D Earth,
            explore ISRO constellations, and export mission-ready reports.
          </p>
          <button type="button" className="btn-primary btn-primary--lg" onClick={onEnter}>
            Enter Mission Control
            <ArrowRight size={18} strokeWidth={1.75} />
          </button>
          <p className="landing-meta">Celestrak catalog · WebSocket telemetry · PDF export</p>
        </div>

        <ul className="landing-features">
          {FEATURES.map(({ icon: Icon, title, desc }) => (
            <li key={title} className="landing-feature">
              <div className="landing-feature-icon"><Icon size={16} strokeWidth={1.75} /></div>
              <div>
                <h3>{title}</h3>
                <p>{desc}</p>
              </div>
            </li>
          ))}
        </ul>
      </main>

      <footer className="landing-bottom">
        {['SGP4 Propagation', 'Live Debris Feed', 'ISRO Focus', 'PDF Reports'].map((item) => (
          <span key={item}>{item}</span>
        ))}
      </footer>
    </section>
  );
}
