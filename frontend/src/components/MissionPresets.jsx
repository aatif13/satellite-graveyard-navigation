import { Globe2, Rocket, Satellite } from 'lucide-react';

const ICONS = { iss: Globe2, isro_eos: Satellite, isro_leo: Rocket };

export default function MissionPresets({ presets, onSelect, activeId }) {
  if (!presets?.length) {
    return <p className="text-[11px] text-slate-600 text-center py-2">Loading presets…</p>;
  }

  return (
    <div className="preset-grid">
      {presets.map((preset) => {
        const Icon = ICONS[preset.id] || Satellite;
        const short = preset.id === 'iss' ? 'ISS' : preset.id === 'isro_eos' ? 'EOS-07' : 'ISRO LEO';
        return (
          <button
            key={preset.id}
            type="button"
            onClick={() => onSelect(preset)}
            className={`preset-btn ${activeId === preset.id ? 'active' : ''}`}
            title={preset.description}
          >
            <Icon size={18} />
            {short}
            <span>{preset.alt_km} km</span>
          </button>
        );
      })}
    </div>
  );
}
