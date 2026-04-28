interface JsonPanelProps {
  title: string;
  value: unknown;
}

export function JsonPanel({ title, value }: JsonPanelProps) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">JSON</p>
          <h3>{title}</h3>
        </div>
      </div>
      <pre className="json-panel">{JSON.stringify(value, null, 2)}</pre>
    </section>
  );
}
