import type { ScoreBreakdown as ScoreBreakdownType } from "../lib/types";

interface ScoreBreakdownProps {
  breakdown: ScoreBreakdownType | null | undefined;
}

const scoreRows: Array<{ key: keyof ScoreBreakdownType; label: string }> = [
  { key: "brief_match", label: "Brief Match" },
  { key: "content_fit", label: "Content Fit" },
  { key: "audience_fit", label: "Audience Fit" },
  { key: "commercial_efficiency", label: "Commercial Efficiency" },
  { key: "growth_signal", label: "Growth Signal" },
];

export function ScoreBreakdown({ breakdown }: ScoreBreakdownProps) {
  if (!breakdown) {
    return <p className="muted-text">Score breakdown unavailable.</p>;
  }

  return (
    <div className="score-breakdown">
      {scoreRows.map((row) => {
        const value = breakdown[row.key] as number;
        return (
          <div className="score-row" key={row.key}>
            <div className="metric-row">
              <span>{row.label}</span>
              <strong>{value.toFixed(1)}</strong>
            </div>
            <div className="score-bar">
              <span style={{ width: `${value}%` }} />
            </div>
          </div>
        );
      })}

      <div className="summary-block slim">
        <h3>Engine notes</h3>
        <ul className="text-list">
          {breakdown.explanation.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
