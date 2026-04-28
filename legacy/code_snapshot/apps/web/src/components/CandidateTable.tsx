import type { CandidateCreator } from "../lib/types";

interface CandidateTableProps {
  candidates: CandidateCreator[];
  onSelect: (candidate: CandidateCreator) => void;
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function CandidateTable({ candidates, onSelect }: CandidateTableProps) {
  return (
    <section className="panel table-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Ranked Candidates</p>
          <h2>Candidate Ranking Demo</h2>
        </div>
      </div>

      {candidates.length > 0 ? (
        <div className="table-wrap">
          <table className="candidate-table">
            <thead>
              <tr>
                <th>Creator</th>
                <th>Type</th>
                <th>Fans</th>
                <th>Price</th>
                <th>Female Ratio</th>
                <th>Median Commercial Play</th>
                <th>Natural CPM</th>
                <th>Monthly Growth</th>
                <th>Final Score</th>
                <th>Recommendation</th>
              </tr>
            </thead>
            <tbody>
              {candidates.map((candidate) => (
                <tr key={candidate.creator_id} onClick={() => onSelect(candidate)}>
                  <td>
                    <button className="table-link" type="button">
                      {candidate.creator_name}
                    </button>
                  </td>
                  <td>{candidate.creator_types.join(" / ")}</td>
                  <td>{candidate.fans_count.toLocaleString()}</td>
                  <td>{candidate.settlement_price_est.toLocaleString()}</td>
                  <td>{formatPercent(candidate.female_ratio)}</td>
                  <td>{candidate.median_commercial_play.toLocaleString()}</td>
                  <td>{candidate.natural_cpm.toFixed(1)}</td>
                  <td>{formatPercent(candidate.monthly_growth_rate)}</td>
                  <td>{candidate.final_score.toFixed(1)}</td>
                  <td>
                    <span className={`status-pill recommendation-${candidate.recommendation_level.toLowerCase()}`}>
                      {candidate.recommendation_level}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="muted-text">Run the pipeline to populate ranked creators.</p>
      )}
    </section>
  );
}
