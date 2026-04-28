import type { CampaignBrief } from "../lib/types";

interface BriefEditorProps {
  rawBrief: string;
  structuredBrief: CampaignBrief | null;
  parserNotes: string[];
  briefDirty: boolean;
  isBusy: boolean;
  onRawChange: (value: string) => void;
  onReset: () => void;
  onStructure: () => void;
}

export function BriefEditor({
  rawBrief,
  structuredBrief,
  parserNotes,
  briefDirty,
  isBusy,
  onRawChange,
  onReset,
  onStructure,
}: BriefEditorProps) {
  return (
    <section className="panel panel-accent">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Campaign Brief</p>
          <h2>Brief Input</h2>
        </div>
        <span className={`status-pill ${briefDirty ? "status-warn" : "status-ok"}`}>
          {briefDirty ? "Needs structuring" : "Structured"}
        </span>
      </div>

      <label className="field-label" htmlFor="brief-input">
        Raw brief text
      </label>
      <textarea
        id="brief-input"
        className="brief-textarea"
        value={rawBrief}
        onChange={(event) => onRawChange(event.target.value)}
        placeholder="Paste a campaign brief here."
      />

      <div className="button-row">
        <button className="ghost-button" onClick={onReset} type="button">
          Reset Sample
        </button>
        <button className="primary-button" disabled={isBusy} onClick={onStructure} type="button">
          {isBusy ? "Structuring..." : "Structure Brief"}
        </button>
      </div>

      <div className="summary-block">
        <h3>Structured snapshot</h3>
        {structuredBrief ? (
          <div className="brief-summary">
            <div className="metric-row">
              <span>{structuredBrief.campaign_name}</span>
              <strong>{structuredBrief.platform}</strong>
            </div>
            <div className="pill-row">
              {structuredBrief.creator_types.map((item) => (
                <span className="tag-pill" key={item}>
                  {item}
                </span>
              ))}
            </div>
            <div className="detail-grid">
              <span>Budget</span>
              <strong>{structuredBrief.budget_total.toLocaleString()}</strong>
              <span>City</span>
              <strong>{structuredBrief.city}</strong>
              <span>Event Date</span>
              <strong>{structuredBrief.event_date}</strong>
            </div>
            <div className="pill-row compact">
              {structuredBrief.content_tags.map((item) => (
                <span className="soft-pill" key={item}>
                  {item}
                </span>
              ))}
            </div>
          </div>
        ) : (
          <p className="muted-text">No structured brief yet.</p>
        )}
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
          <p className="muted-text">Parser output will appear here.</p>
        )}
      </div>
    </section>
  );
}
