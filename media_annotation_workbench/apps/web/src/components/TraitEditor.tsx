import type { TraitItem } from "../lib/types";

interface TraitEditorProps {
  value: TraitItem[];
  onChange: (value: TraitItem[]) => void;
}

function updateItem(items: TraitItem[], index: number, patch: Partial<TraitItem>) {
  return items.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item));
}

export function TraitEditor({ value, onChange }: TraitEditorProps) {
  return (
    <div className="trait-editor">
      <div className="section-actions">
        <h4>达人特征</h4>
        <button
          className="ghost-button small"
          onClick={() =>
            onChange([
              ...value,
              { trait_name: "", value: "", confidence: 0.5, evidence_message_ids: [], rationale: "" },
            ])
          }
          type="button"
        >
          新增特征
        </button>
      </div>
      {value.length === 0 ? <p className="muted-text">当前没有人工编辑的达人特征，保存草稿后会覆盖审核视图。</p> : null}
      {value.map((item, index) => (
        <div className="trait-card" key={`${item.trait_name}-${index}`}>
          <div className="trait-grid">
            <label className="field-block">
              <span>特征名</span>
              <input
                value={item.trait_name}
                onChange={(event) => onChange(updateItem(value, index, { trait_name: event.target.value }))}
              />
            </label>
            <label className="field-block">
              <span>特征值</span>
              <input
                value={item.value}
                onChange={(event) => onChange(updateItem(value, index, { value: event.target.value }))}
              />
            </label>
            <label className="field-block">
              <span>置信度</span>
              <input
                type="number"
                max={1}
                min={0}
                step={0.01}
                value={item.confidence ?? 0}
                onChange={(event) => onChange(updateItem(value, index, { confidence: Number(event.target.value) }))}
              />
            </label>
            <label className="field-block">
              <span>证据消息ID</span>
              <input
                value={(item.evidence_message_ids ?? []).join(",")}
                onChange={(event) =>
                  onChange(
                    updateItem(value, index, {
                      evidence_message_ids: event.target.value
                        .split(",")
                        .map((part) => part.trim())
                        .filter(Boolean),
                    }),
                  )
                }
              />
            </label>
          </div>

          <label className="field-block">
            <span>判断依据</span>
            <textarea
              rows={3}
              value={item.rationale ?? ""}
              onChange={(event) => onChange(updateItem(value, index, { rationale: event.target.value }))}
            />
          </label>

          <button
            className="ghost-button small danger"
            onClick={() => onChange(value.filter((_, itemIndex) => itemIndex !== index))}
            type="button"
          >
            删除
          </button>
        </div>
      ))}
    </div>
  );
}
