import { useEffect, useState } from "react";

import { fetchDocument } from "../lib/api";
import type { DashboardSummary, DocumentResponse } from "../lib/types";

interface DocsPageProps {
  token: string;
  summary: DashboardSummary | null;
}

const docOptions = [
  { key: "tag_dictionary", label: "tag_dictionary.yaml" },
  { key: "annotation_guideline", label: "annotation_guideline.md" },
  { key: "asset_field_guide", label: "asset_field_guide.md" },
];

export function DocsPage({ token, summary }: DocsPageProps) {
  const [docType, setDocType] = useState("asset_field_guide");
  const [document, setDocument] = useState<DocumentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadDocument() {
      try {
        const response = await fetchDocument(token, docType, summary?.active_snapshot?.snapshot_id);
        setDocument(response);
        setError(null);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "文档加载失败");
      }
    }
    void loadDocument();
  }, [docType, token, summary?.active_snapshot?.snapshot_id]);

  return (
    <div className="page-stack">
      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Schema & Docs</p>
            <h2>口径文档与字段说明</h2>
          </div>
        </div>

        <div className="selector-grid">
          {docOptions.map((option) => (
            <button
              key={option.key}
              className={`selector-chip ${docType === option.key ? "selector-chip-active" : ""}`}
              onClick={() => setDocType(option.key)}
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>
      </section>

      {error ? <div className="error-banner">{error}</div> : null}
      {document ? (
        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Document</p>
              <h3>{document.doc_type}</h3>
            </div>
          </div>
          <pre className="doc-panel">{document.content}</pre>
        </section>
      ) : null}
    </div>
  );
}
