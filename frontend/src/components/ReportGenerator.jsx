import { jsPDF } from 'jspdf';
import { Download } from 'lucide-react';

/** jsPDF default font is ASCII-only; strip/replace Unicode before doc.text(). */
function pdfSafeText(text) {
  return String(text ?? '')
    .replace(/\u2192/g, '->')
    .replace(/\u2014/g, '-')
    .replace(/\u00b7/g, '-')
    .replace(/[^\x20-\x7E]/g, '');
}

export function generateMissionReport({ waypoints, analysis, missionName, isroMissions }) {
  const doc = new jsPDF();
  const score = analysis?.risk_score ?? 0;
  const level = score > 70 ? 'DANGEROUS' : score > 40 ? 'CAUTION' : 'SAFE';

  doc.setFillColor(3, 7, 18);
  doc.rect(0, 0, 210, 297, 'F');
  doc.setTextColor(6, 182, 212);
  doc.setFontSize(18);
  doc.text('SATELLITE GRAVEYARD NAVIGATOR', 14, 20);
  doc.setFontSize(10);
  doc.setTextColor(148, 163, 184);
  doc.text('Mission Risk Report - FAR AWAY 2026 - ISRO-Ready Analysis', 14, 28);

  doc.setTextColor(255, 255, 255);
  doc.setFontSize(14);
  doc.text(pdfSafeText(missionName || 'Proposed Orbit Mission'), 14, 42);

  const [r, g, b] = score > 50 ? [239, 68, 68] : [34, 197, 94];
  doc.setFontSize(11);
  doc.setTextColor(r, g, b);
  doc.text(`RISK SCORE: ${score}/100 - ${level}`, 14, 54);

  doc.setTextColor(200, 200, 200);
  doc.setFontSize(9);
  let y = 66;

  if (waypoints?.length) {
    doc.setTextColor(6, 182, 212);
    doc.setFontSize(10);
    doc.text('Orbit Waypoints', 14, y);
    y += 8;
    doc.setTextColor(180, 180, 180);
    doc.setFontSize(8);
    waypoints.forEach((wp, i) => {
      doc.text(
        `• WP${i + 1}: ${wp.lat?.toFixed(2)}°, ${wp.lng?.toFixed(2)}° @ ${wp.alt_km ?? '—'} km`,
        14, y,
      );
      y += 6;
    });
    y += 4;
    doc.setFontSize(9);
    doc.setTextColor(200, 200, 200);
  }

  [
    `Nearby debris objects: ${analysis?.nearby_count ?? 0}`,
    `Recommended safe altitude: ${analysis?.safe_altitude ?? '—'} km`,
    `Velocity-crossing: ${analysis?.risk_breakdown?.velocity_crossing ?? '—'} pts`,
    `Density: ${analysis?.risk_breakdown?.density ?? '—'} pts`,
    `Altitude overlap: ${analysis?.risk_breakdown?.altitude_overlap ?? '—'} pts`,
  ].forEach((line) => { doc.text(line, 14, y); y += 7; });

  y += 4;
  doc.setTextColor(249, 115, 22);
  doc.setFontSize(10);
  doc.text('ISRO Constellation Context', 14, y);
  y += 8;
  doc.setTextColor(180, 180, 180);
  doc.setFontSize(8);
  (isroMissions || []).slice(0, 5).forEach((m) => {
    doc.text(pdfSafeText(`• ${m.name} (${m.type}) @ ${m.alt_km}km`), 14, y);
    y += 6;
  });

  y += 4;
  doc.setTextColor(6, 182, 212);
  doc.setFontSize(10);
  doc.text('Critical Conjunction Objects', 14, y);
  y += 8;
  doc.setTextColor(180, 180, 180);
  doc.setFontSize(8);
  const critical = analysis?.critical_objects || [];
  if (!critical.length) {
    doc.text('No high-risk crossing debris in band.', 14, y);
    y += 6;
  } else {
    critical.slice(0, 6).forEach((obj) => {
      const label = obj.name?.startsWith('1 ') || obj.name?.startsWith('2 ')
        ? `NORAD ${obj.norad_id || '?'}`
        : obj.name;
      doc.text(
        pdfSafeText(
          `• ${label} @ ${obj.alt_km}km (crossing: ${obj.crossing_factor})${obj.is_isro ? ' [ISRO]' : ''}`,
        ),
        14, y,
      );
      y += 6;
    });
  }

  y += 4;
  doc.setTextColor(6, 182, 212);
  doc.setFontSize(10);
  doc.text('Launch Window Recommendations (Next 7 Days)', 14, y);
  y += 8;
  doc.setTextColor(180, 180, 180);
  doc.setFontSize(8);
  (analysis?.launch_windows || []).slice(0, 5).forEach((w) => {
    doc.text(
      pdfSafeText(
        `• ${w.date} ${String(w.utc_hour).padStart(2, '0')}:00 UTC - ${w.risk_pct}% risk [${w.label}]`,
      ),
      14, y,
    );
    y += 6;
  });

  doc.setTextColor(100, 116, 139);
  doc.setFontSize(7);
  doc.text('Data: Celestrak TLE - SGP4 - Velocity-aware conjunction analysis', 14, 280);
  doc.text(`Generated: ${new Date().toISOString()}`, 14, 285);
  doc.save(`mission-risk-report-${Date.now()}.pdf`);
}

export default function ReportButton({ waypoints, analysis, missionName, isroMissions }) {
  return (
    <button
      type="button"
      onClick={() => generateMissionReport({ waypoints, analysis, missionName, isroMissions })}
      disabled={!analysis}
      className="btn-outline btn-outline--block"
    >
      <Download size={14} />
      Download Report
    </button>
  );
}
