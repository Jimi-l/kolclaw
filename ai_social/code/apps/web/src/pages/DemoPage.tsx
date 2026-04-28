import { useEffect, useState } from "react";

import { fetchShortlistReferences, parseShortlistBrief, previewShortlistPlan, runShortlist } from "../lib/api";
import type {
  ExternalDocReference,
  ShortlistCandidate,
  ShortlistRequirement,
  ShortlistRunMetadata,
  ShortlistSearchPlan,
  XingtuCreatorDetail,
} from "../lib/types";

const defaultRawBrief = `Brand: Luminelle
Product: Velvet Lip Glaze
SKU: V06
Platform: douyin
City: shanghai
Budget: 80000 RMB
Target audience: female office workers, beauty shoppers
KPI: stable views, completion rate, cost efficiency
Style: polished beauty tutorial, seeding
Tone: premium, trustworthy
Avoid: parenting, pets
Must: beauty creators with female audience
Prefer: shanghai-based creators with recent growth
Notes: shortlist five creators for the first review`;

const defaultAccountName = "Demo Workspace Account 001";

function formatNumber(value?: number | null) {
  if (value === null || value === undefined) {
    return "—";
  }
  return value.toLocaleString();
}

function formatRatio(value?: number | null) {
  if (value === null || value === undefined) {
    return "—";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function renderPills(values: string[], kind: "tag" | "soft" = "tag") {
  if (values.length === 0) {
    return <p className="muted-text">None</p>;
  }
  return (
    <div className="pill-row compact">
      {values.map((value) => (
        <span className={kind === "tag" ? "tag-pill" : "soft-pill"} key={value}>
          {value}
        </span>
      ))}
    </div>
  );
}

export function DemoPage() {
  const [rawBrief, setRawBrief] = useState(defaultRawBrief);
  const [accountName, setAccountName] = useState(defaultAccountName);
  const [collectionLimit, setCollectionLimit] = useState(5);
  const [shortlistLimit, setShortlistLimit] = useState(3);
  const [structuredRequirement, setStructuredRequirement] = useState<ShortlistRequirement | null>(null);
  const [parserNotes, setParserNotes] = useState<string[]>([]);
  const [searchPlan, setSearchPlan] = useState<ShortlistSearchPlan | null>(null);
  const [referenceDocs, setReferenceDocs] = useState<ExternalDocReference[]>([]);
  const [collectedCreators, setCollectedCreators] = useState<XingtuCreatorDetail[]>([]);
  const [shortlist, setShortlist] = useState<ShortlistCandidate[]>([]);
  const [metadata, setMetadata] = useState<ShortlistRunMetadata | null>(null);
  const [briefDirty, setBriefDirty] = useState(true);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function bootstrap() {
      try {
        const response = await fetchShortlistReferences();
        setReferenceDocs(response.references);
      } catch (caughtError) {
        setError(caughtError instanceof Error ? caughtError.message : "Failed to load reference docs.");
      }
    }

    void bootstrap();
  }, []);

  async function handleParse() {
    setIsBusy(true);
    setError(null);
    try {
      const response = await parseShortlistBrief({ raw_text: rawBrief });
      setStructuredRequirement(response.structured_requirement);
      setParserNotes(response.parser_notes);
      setBriefDirty(false);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Brief parsing failed.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handlePlan() {
    setIsBusy(true);
    setError(null);
    try {
      const response = await previewShortlistPlan({
        raw_text: rawBrief,
        collection_limit: collectionLimit,
        shortlist_limit: shortlistLimit,
      });
      setStructuredRequirement(response.structured_requirement);
      setParserNotes(response.parser_notes);
      setSearchPlan(response.search_plan);
      setReferenceDocs(response.reference_docs);
      setBriefDirty(false);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to preview shortlist plan.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleRun() {
    setIsBusy(true);
    setError(null);
    try {
      const response = await runShortlist({
        raw_text: rawBrief,
        account_name: accountName,
        collection_limit: collectionLimit,
        shortlist_limit: shortlistLimit,
        headless: true,
      });
      setStructuredRequirement(response.structured_requirement);
      setParserNotes(response.parser_notes);
      setSearchPlan(response.search_plan);
      setCollectedCreators(response.collected_creators);
      setShortlist(response.shortlist);
      setReferenceDocs(response.reference_docs);
      setMetadata(response.metadata);
      setBriefDirty(false);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Shortlist run failed.");
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">KOLClaw V1</p>
          <h1>AI Media Shortlist Assistant</h1>
          <p className="hero-copy">
            Brief intake, deterministic requirement parsing, Xingtu live search, creator extraction, and heuristic
            shortlist ranking in one narrow V1 demo flow.
          </p>
        </div>
        <div className="hero-stat">
          <span>{shortlist.length}</span>
          <small>Shortlist creators</small>
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      <main className="demo-grid">
        <div className="left-column">
          <section className="panel panel-accent">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Brief Intake</p>
                <h2>Raw Brief</h2>
              </div>
              <span className={`status-pill ${briefDirty ? "status-warn" : "status-ok"}`}>
                {briefDirty ? "Needs refresh" : "Ready"}
              </span>
            </div>

            <label className="field-label" htmlFor="brief-input">
              Brief text
            </label>
            <textarea
              id="brief-input"
              className="brief-textarea"
              value={rawBrief}
              onChange={(event) => {
                setRawBrief(event.target.value);
                setBriefDirty(true);
              }}
            />

            <div className="config-grid">
              <label>
                <span className="field-label">Workspace account</span>
                <input
                  className="template-select"
                  value={accountName}
                  onChange={(event) => setAccountName(event.target.value)}
                  placeholder="Optional Xingtu workspace name"
                />
              </label>
              <label>
                <span className="field-label">Collect top rows</span>
                <input
                  className="template-select"
                  min={1}
                  max={10}
                  type="number"
                  value={collectionLimit}
                  onChange={(event) => setCollectionLimit(Number(event.target.value) || 1)}
                />
              </label>
              <label>
                <span className="field-label">Shortlist size</span>
                <input
                  className="template-select"
                  min={1}
                  max={10}
                  type="number"
                  value={shortlistLimit}
                  onChange={(event) => setShortlistLimit(Number(event.target.value) || 1)}
                />
              </label>
            </div>

            <div className="button-stack">
              <button className="ghost-button" disabled={isBusy} onClick={handleParse} type="button">
                {isBusy ? "Parsing..." : "1. Parse Requirement"}
              </button>
              <button className="ghost-button" disabled={isBusy} onClick={handlePlan} type="button">
                {isBusy ? "Planning..." : "2. Preview Search Plan"}
              </button>
              <button className="primary-button" disabled={isBusy} onClick={handleRun} type="button">
                {isBusy ? "Running live shortlist..." : "3. Run Live Shortlist"}
              </button>
            </div>

            <div className="summary-block">
              <h3>Parser notes</h3>
              {parserNotes.length > 0 ? (
                <ul className="text-list">
                  {parserNotes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              ) : (
                <p className="muted-text">Run parsing to extract a normalized requirement object.</p>
              )}
            </div>
          </section>
        </div>

        <div className="center-column">
          <section className="panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Structured Requirement</p>
                <h2>Requirement Snapshot</h2>
              </div>
            </div>

            {structuredRequirement ? (
              <div className="stack">
                <div className="detail-grid">
                  <span>Brand</span>
                  <strong>{structuredRequirement.brand ?? "—"}</strong>
                  <span>Product</span>
                  <strong>{structuredRequirement.product_name ?? "—"}</strong>
                  <span>SKU</span>
                  <strong>{structuredRequirement.product_sku ?? "—"}</strong>
                  <span>Category</span>
                  <strong>{structuredRequirement.product_category ?? "—"}</strong>
                  <span>Budget</span>
                  <strong>{formatNumber(structuredRequirement.budget_total)}</strong>
                  <span>City</span>
                  <strong>{structuredRequirement.city ?? "—"}</strong>
                </div>

                <div className="summary-block slim">
                  <h3>Target audience</h3>
                  {renderPills(structuredRequirement.target_audience, "tag")}
                </div>
                <div className="summary-block slim">
                  <h3>KPI goals</h3>
                  {renderPills(structuredRequirement.kpi_goals, "soft")}
                </div>
                <div className="summary-block slim">
                  <h3>Hard constraints</h3>
                  <div className="detail-grid">
                    <span>Min fans</span>
                    <strong>{formatNumber(structuredRequirement.hard_constraints.min_fans_count)}</strong>
                    <span>Budget cap / creator</span>
                    <strong>{formatNumber(structuredRequirement.hard_constraints.budget_cap_per_creator)}</strong>
                  </div>
                  {renderPills(structuredRequirement.hard_constraints.creator_categories, "tag")}
                  {structuredRequirement.exclusions.length > 0 ? (
                    <div className="pill-row compact">
                      {structuredRequirement.exclusions.map((value) => (
                        <span className="risk-pill" key={value}>
                          Avoid {value}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            ) : (
              <p className="muted-text">No parsed requirement yet.</p>
            )}
          </section>

          <section className="panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Search Plan</p>
                <h2>Xingtu Execution Plan</h2>
              </div>
            </div>

            {searchPlan ? (
              <div className="stack">
                <div className="summary-block slim">
                  <h3>Live filters</h3>
                  {Object.keys(searchPlan.filter_config.named_filters).length > 0 ? (
                    <ul className="text-list">
                      {Object.entries(searchPlan.filter_config.named_filters).map(([key, values]) => (
                        <li key={key}>
                          {key}: {values.join(", ")}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted-text">No hardened live dropdown filters selected.</p>
                  )}
                </div>
                <div className="summary-block slim">
                  <h3>Generated keywords</h3>
                  {renderPills(searchPlan.generated_keywords, "soft")}
                </div>
                <div className="summary-block slim">
                  <h3>Ranking priorities</h3>
                  <ul className="text-list">
                    {searchPlan.ranking_priorities.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
                {searchPlan.unapplied_constraints.length > 0 ? (
                  <div className="summary-block slim">
                    <h3>Not yet applied live</h3>
                    <ul className="text-list">
                      {searchPlan.unapplied_constraints.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="muted-text">Preview the plan to see the Xingtu-oriented filter mapping.</p>
            )}
          </section>

          <section className="panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Collected Creators</p>
                <h2>Live Extraction Output</h2>
              </div>
            </div>

            {collectedCreators.length > 0 ? (
              <div className="table-shell">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Creator tags</th>
                      <th>Fans</th>
                      <th>Play median</th>
                      <th>Expected CPM</th>
                      <th>Growth</th>
                    </tr>
                  </thead>
                  <tbody>
                    {collectedCreators.map((creator) => (
                      <tr key={creator.creator_id ?? creator.creator_name}>
                        <td>
                          <strong>{creator.creator_name ?? "Unknown"}</strong>
                        </td>
                        <td>{creator.creator_types.slice(0, 3).join(" / ") || "—"}</td>
                        <td>{formatNumber(creator.fans_count)}</td>
                        <td>{formatNumber(creator.avg_video_play_median)}</td>
                        <td>{creator.expected_cpm ?? "—"}</td>
                        <td>{formatRatio(creator.monthly_growth_rate)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted-text">Run the live shortlist to collect Xingtu creator profiles.</p>
            )}
          </section>
        </div>

        <div className="right-column">
          <section className="panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Ranked Shortlist</p>
                <h2>Recommendation Output</h2>
              </div>
            </div>

            {shortlist.length > 0 ? (
              <div className="stack">
                {shortlist.map((item) => (
                  <article className="shortlist-card" key={item.creator.creator_id ?? item.creator.creator_name}>
                    <div className="shortlist-header">
                      <div>
                        <h3>{item.creator.creator_name ?? "Unknown creator"}</h3>
                        <p className="muted-text">{item.recommendation_level}</p>
                      </div>
                      <div className="score-chip">{item.score_breakdown.total_score.toFixed(1)}</div>
                    </div>

                    <p className="candidate-reason">{item.recommendation_reason}</p>
                    {renderPills(item.creator.creator_types.slice(0, 5), "soft")}

                    <div className="detail-grid compact-grid">
                      <span>Fans</span>
                      <strong>{formatNumber(item.creator.fans_count)}</strong>
                      <span>Play median</span>
                      <strong>{formatNumber(item.creator.avg_video_play_median)}</strong>
                      <span>Expected CPM</span>
                      <strong>{item.creator.expected_cpm ?? "—"}</strong>
                      <span>Growth</span>
                      <strong>{formatRatio(item.creator.monthly_growth_rate)}</strong>
                    </div>

                    <div className="score-grid">
                      <div>
                        <span>Brief</span>
                        <strong>{item.score_breakdown.brief_match.toFixed(0)}</strong>
                      </div>
                      <div>
                        <span>Audience</span>
                        <strong>{item.score_breakdown.audience_match.toFixed(0)}</strong>
                      </div>
                      <div>
                        <span>Content</span>
                        <strong>{item.score_breakdown.content_fit.toFixed(0)}</strong>
                      </div>
                      <div>
                        <span>Quality</span>
                        <strong>{item.score_breakdown.quality_activity.toFixed(0)}</strong>
                      </div>
                      <div>
                        <span>Commercial</span>
                        <strong>{item.score_breakdown.commercial_signal.toFixed(0)}</strong>
                      </div>
                      <div>
                        <span>Risk</span>
                        <strong>{item.score_breakdown.risk_penalty.toFixed(0)}</strong>
                      </div>
                    </div>

                    {item.risk_flags.length > 0 ? (
                      <div className="pill-row compact">
                        {item.risk_flags.map((flag) => (
                          <span className="risk-pill" key={flag}>
                            {flag}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : (
              <p className="muted-text">The shortlist will appear here after the live Xingtu run finishes.</p>
            )}
          </section>

          <section className="panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Operational References</p>
                <h2>Docs Used In V1</h2>
              </div>
            </div>

            {referenceDocs.length > 0 ? (
              <div className="stack">
                {referenceDocs.map((doc) => (
                  <div className="doc-card" key={doc.doc_id}>
                    <div className="metric-row">
                      <strong>{doc.title}</strong>
                      <span className="soft-pill">{doc.source_type.toUpperCase()}</span>
                    </div>
                    <p className="muted-text">{doc.relative_path}</p>
                    {doc.usage_notes.length > 0 ? (
                      <ul className="text-list compact-list">
                        {doc.usage_notes.map((note) => (
                          <li key={note}>{note}</li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted-text">Reference docs will load here.</p>
            )}
          </section>

          <section className="panel">
            <div className="panel-header">
              <div>
                <p className="eyebrow">Run Metadata</p>
                <h2>Live Execution State</h2>
              </div>
            </div>

            {metadata ? (
              <div className="detail-grid">
                <span>Rows seen</span>
                <strong>{metadata.rows_seen}</strong>
                <span>Creators collected</span>
                <strong>{metadata.creators_collected}</strong>
                <span>Shortlist count</span>
                <strong>{metadata.creators_ranked}</strong>
                <span>Storage state</span>
                <strong className="truncate-text">{metadata.storage_state_path}</strong>
                <span>Search page</span>
                <strong className="truncate-text">{metadata.creator_search_url ?? "—"}</strong>
              </div>
            ) : (
              <p className="muted-text">Run metadata will appear after the live shortlist call.</p>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
