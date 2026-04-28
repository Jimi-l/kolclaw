import type { StrategyTemplate } from "../lib/types";

interface TemplateSelectorProps {
  templates: StrategyTemplate[];
  selectedTemplateId: string;
  isBusy: boolean;
  onTemplateChange: (templateId: string) => void;
  onGeneratePlan: () => void;
  onRun: () => void;
}

export function TemplateSelector({
  templates,
  selectedTemplateId,
  isBusy,
  onTemplateChange,
  onGeneratePlan,
  onRun,
}: TemplateSelectorProps) {
  const selectedTemplate = templates.find((template) => template.template_id === selectedTemplateId) ?? null;

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Strategy Template</p>
          <h2>Selection Strategy</h2>
        </div>
      </div>

      <label className="field-label" htmlFor="template-select">
        Template
      </label>
      <select
        id="template-select"
        className="template-select"
        value={selectedTemplateId}
        onChange={(event) => onTemplateChange(event.target.value)}
      >
        {templates.map((template) => (
          <option key={template.template_id} value={template.template_id}>
            {template.template_name}
          </option>
        ))}
      </select>

      {selectedTemplate ? (
        <div className="template-card">
          <p>{selectedTemplate.description}</p>
          <div className="pill-row compact">
            {selectedTemplate.soft_preferences.preferred_content_tags.map((item) => (
              <span className="soft-pill" key={item}>
                {item}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      <div className="button-row">
        <button className="ghost-button" disabled={isBusy} onClick={onGeneratePlan} type="button">
          Preview Plan
        </button>
        <button className="primary-button" disabled={isBusy} onClick={onRun} type="button">
          {isBusy ? "Running..." : "Run Ranking"}
        </button>
      </div>
    </section>
  );
}
