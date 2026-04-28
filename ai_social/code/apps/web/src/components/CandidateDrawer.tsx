import type { CandidateCreator } from "../lib/types";

import { ScoreBreakdown } from "./ScoreBreakdown";

interface CandidateDrawerProps {
  candidate: CandidateCreator | null;
  onClose: () => void;
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function CandidateDrawer({ candidate, onClose }: CandidateDrawerProps) {
  return (
    <aside className={`drawer ${candidate ? "drawer-open" : ""}`}>
      <div className="drawer-header">
        <div>
          <p className="eyebrow">Candidate Detail</p>
          <h2>{candidate?.creator_name ?? "No selection"}</h2>
        </div>
        <button className="ghost-button" onClick={onClose} type="button">
          Close
        </button>
      </div>

      {candidate ? (
        <div className="drawer-content">
          <div className="summary-block">
            <h3>Basic profile</h3>
            <div className="detail-grid">
              <span>Types</span>
              <strong>{candidate.creator_types.join(", ")}</strong>
              <span>City</span>
              <strong>{candidate.city ?? "n/a"}</strong>
              <span>Fans</span>
              <strong>{candidate.fans_count.toLocaleString()}</strong>
              <span>Female Ratio</span>
              <strong>{formatPercent(candidate.female_ratio)}</strong>
              <span>Settlement</span>
              <strong>{candidate.settlement_price_est.toLocaleString()}</strong>
              <span>Commercial Play</span>
              <strong>{candidate.median_commercial_play.toLocaleString()}</strong>
            </div>
          </div>

          <div className="summary-block">
            <h3>Recommendation reason</h3>
            <p>{candidate.recommendation_reason}</p>
          </div>

          <div className="summary-block">
            <h3>Risk notes</h3>
            {candidate.risk_notes.length > 0 ? (
              <ul className="text-list">
                {candidate.risk_notes.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="muted-text">No material flags surfaced in the v1 rule set.</p>
            )}
          </div>

          <div className="summary-block">
            <h3>Recent content summary</h3>
            <p>{candidate.recent_content_summary}</p>
          </div>

          <div className="summary-block">
            <h3>Recent curve summary</h3>
            <p>{candidate.recent_curve_summary}</p>
          </div>

          <div className="summary-block">
            <h3>Score breakdown</h3>
            <ScoreBreakdown breakdown={candidate.score_breakdown} />
          </div>
        </div>
      ) : (
        <p className="muted-text">Select a ranked creator to inspect details.</p>
      )}
    </aside>
  );
}
