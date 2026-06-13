import { Globe2, Rocket, Satellite, Sun } from 'lucide-react';

const ICONS = {
  iss: Globe2,
  isro_eos: Satellite,
  isro_leo: Rocket,
  chandrayaan_3: Rocket,
  aditya_l1: Sun,
};

const SHORT = {
  iss: 'ISS',
  isro_eos: 'EOS-07',
  isro_leo: 'ISRO LEO',
  chandrayaan_3: 'Chandrayaan-3',
  aditya_l1: 'Aditya-L1',
};

export default function MissionPresets({ presets, onSelect, activeId }) {
  if (!presets?.length) {
    return <p className="field-hint">Loading presets…</p>;
  }

  const activePreset = presets.find((p) => p.id === activeId);

  return (
    <>
      <div className="preset-grid">
        {presets.map((preset) => {
          const Icon = ICONS[preset.id] || Satellite;
          const short = SHORT[preset.id] || preset.name;
          return (
            <button
              key={preset.id}
              type="button"
              onClick={() => onSelect(preset)}
              className={`preset-btn ${activeId === preset.id ? 'active' : ''} ${preset.agency === 'ISRO' ? 'preset-btn--isro' : ''}`}
              title={preset.description}
            >
              <Icon size={18} />
              {short}
              <span>{preset.alt_km} km</span>
            </button>
          );
        })}
      </div>
      {activePreset?.isro_story && (
        <p className="preset-isro-story">{activePreset.isro_story}</p>
      )}
    </>
  );
}
