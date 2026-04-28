import { JsonPanel } from "./JsonPanel";

interface DetailDrawerProps {
  title: string;
  subtitle?: string;
  rawItem?: Record<string, unknown> | null;
  reviewedItem?: Record<string, unknown> | null;
  related?: Record<string, Record<string, unknown>[]>;
  content?: string | null;
  format?: string | null;
  onClose: () => void;
}

export function DetailDrawer({
  title,
  subtitle,
  rawItem,
  reviewedItem,
  related,
  content,
  format,
  onClose,
}: DetailDrawerProps) {
  return (
    <aside className="detail-drawer">
      <div className="drawer-header">
        <div>
          <p className="eyebrow">详情</p>
          <h2>{title}</h2>
          {subtitle ? <p className="muted-text">{subtitle}</p> : null}
        </div>
        <button className="ghost-button small" onClick={onClose} type="button">
          关闭
        </button>
      </div>

      {content ? (
        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">文档</p>
              <h3>{format === "yaml" ? "YAML 内容" : "Markdown 内容"}</h3>
            </div>
          </div>
          <pre className="doc-panel">{content}</pre>
        </section>
      ) : null}

      {reviewedItem ? <JsonPanel title="Reviewed View" value={reviewedItem} /> : null}
      {rawItem ? <JsonPanel title="Raw View" value={rawItem} /> : null}

      {related && Object.keys(related).length > 0 ? (
        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">关联记录</p>
              <h3>Related Assets</h3>
            </div>
          </div>
          <div className="related-groups">
            {Object.entries(related).map(([key, items]) => (
              <div className="related-group" key={key}>
                <strong>{key}</strong>
                <p className="muted-text">{items.length} 条</p>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </aside>
  );
}
