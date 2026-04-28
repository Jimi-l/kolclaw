import type { PipelineMetadata, RetrievalPlan } from "../lib/types";

interface RetrievalPlanPanelProps {
  plan: RetrievalPlan | null;
  metadata: PipelineMetadata | null;
}

export function RetrievalPlanPanel({ plan, metadata }: RetrievalPlanPanelProps) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Retrieval Plan</p>
          <h2>Planner Output</h2>
        </div>
      </div>

      {plan ? (
        <div className="plan-layout">
          <div className="summary-block">
            <h3>Selected filters</h3>
            <div className="filter-grid">
              {Object.entries(plan.selected_filters).map(([key, value]) => (
                <div className="filter-item" key={key}>
                  <span>{key}</span>
                  <strong>{String(value)}</strong>
                </div>
              ))}
            </div>
          </div>

          <div className="summary-block">
            <h3>Generated keywords</h3>
            <div className="pill-row compact">
              {plan.generated_keywords.map((keyword) => (
                <span className="soft-pill" key={keyword}>
                  {keyword}
                </span>
              ))}
            </div>
          </div>

          <div className="two-column-block">
            <div className="summary-block">
              <h3>Hard filter summary</h3>
              <ul className="text-list">
                {plan.hard_filter_summary.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="summary-block">
              <h3>Ranking priorities</h3>
              <ul className="text-list">
                {plan.ranking_priorities.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>

          {metadata ? (
            <div className="summary-block">
              <h3>Run metadata</h3>
              <div className="detail-grid">
                <span>Loaded</span>
                <strong>{metadata.total_candidates_loaded}</strong>
                <span>Passed filters</span>
                <strong>{metadata.candidates_after_filters}</strong>
                <span>Filtered out</span>
                <strong>{metadata.filtered_out}</strong>
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <p className="muted-text">Generate a plan to inspect filters and ranking priorities.</p>
      )}
    </section>
  );
}
