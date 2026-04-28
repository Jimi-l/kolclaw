import { useEffect, useState } from "react";

import { BriefEditor } from "../components/BriefEditor";
import { CandidateDrawer } from "../components/CandidateDrawer";
import { CandidateTable } from "../components/CandidateTable";
import { RetrievalPlanPanel } from "../components/RetrievalPlanPanel";
import { TemplateSelector } from "../components/TemplateSelector";
import { fetchSample, fetchTemplates, generateRetrievalPlan, runCandidates, structureBrief } from "../lib/api";
import type {
  CampaignBrief,
  CandidateCreator,
  PipelineMetadata,
  RetrievalPlan,
  StrategyTemplate,
} from "../lib/types";

const defaultRawBrief = `Campaign: Shanghai Spring Offline Show Push
Platform: douyin
Budget: 132000 RMB
City: shanghai
Event date: 2026-05-20
Creator types: fashion, beauty, stylish
Content focus: outfit, show, transition, runway, event vlog
Style direction: stylish, premium, city chic
Need creators who can cover an offline show with quick-turn polished clips.`;

export function DemoPage() {
  const [rawBrief, setRawBrief] = useState(defaultRawBrief);
  const [templates, setTemplates] = useState<StrategyTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [structuredBrief, setStructuredBrief] = useState<CampaignBrief | null>(null);
  const [parserNotes, setParserNotes] = useState<string[]>([]);
  const [retrievalPlan, setRetrievalPlan] = useState<RetrievalPlan | null>(null);
  const [metadata, setMetadata] = useState<PipelineMetadata | null>(null);
  const [candidates, setCandidates] = useState<CandidateCreator[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateCreator | null>(null);
  const [briefDirty, setBriefDirty] = useState(true);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function bootstrap() {
      setIsBusy(true);
      setError(null);
      try {
        const [templateList, sample] = await Promise.all([fetchTemplates(), fetchSample()]);
        setTemplates(templateList);
        setSelectedTemplateId(sample.template.template_id || templateList[0]?.template_id || "");
        setStructuredBrief(sample.brief);
        setParserNotes(["Loaded sample brief from the local mock dataset."]);
        setRetrievalPlan(sample.retrieval_plan);
        setMetadata(sample.metadata);
        setCandidates(sample.candidates);
        setSelectedCandidate(sample.candidates[0] ?? null);
        setBriefDirty(false);
      } catch (caughtError) {
        setError(caughtError instanceof Error ? caughtError.message : "Failed to load demo data.");
      } finally {
        setIsBusy(false);
      }
    }

    void bootstrap();
  }, []);

  async function ensureStructuredBrief() {
    if (structuredBrief && !briefDirty) {
      return structuredBrief;
    }

    const response = await structureBrief({ raw_text: rawBrief });
    setStructuredBrief(response.structured_brief);
    setParserNotes(response.parser_notes);
    setBriefDirty(false);
    return response.structured_brief;
  }

  async function handleStructure() {
    setIsBusy(true);
    setError(null);
    try {
      await ensureStructuredBrief();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Brief parsing failed.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleGeneratePlan() {
    if (!selectedTemplateId) {
      return;
    }

    setIsBusy(true);
    setError(null);
    try {
      const brief = await ensureStructuredBrief();
      const plan = await generateRetrievalPlan({ brief, template_id: selectedTemplateId });
      setRetrievalPlan(plan);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Failed to build retrieval plan.");
    } finally {
      setIsBusy(false);
    }
  }

  async function handleRun() {
    if (!selectedTemplateId) {
      return;
    }

    setIsBusy(true);
    setError(null);
    try {
      const brief = await ensureStructuredBrief();
      const response = await runCandidates({ brief, template_id: selectedTemplateId, limit: 20 });
      setRetrievalPlan(response.retrieval_plan);
      setMetadata(response.metadata);
      setCandidates(response.candidates);
      setSelectedCandidate(response.candidates[0] ?? null);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Candidate ranking failed.");
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">KOLClaw</p>
          <h1>Brief-Driven Candidate Ranking Demo</h1>
          <p className="hero-copy">
            Deterministic scaffold for turning a campaign brief and a reusable strategy template into a ranked
            creator list.
          </p>
        </div>
        <div className="hero-stat">
          <span>{candidates.length}</span>
          <small>Ranked results in view</small>
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      <main className="demo-grid">
        <div className="left-column">
          <BriefEditor
            rawBrief={rawBrief}
            structuredBrief={structuredBrief}
            parserNotes={parserNotes}
            briefDirty={briefDirty}
            isBusy={isBusy}
            onRawChange={(value) => {
              setRawBrief(value);
              setBriefDirty(true);
            }}
            onReset={() => {
              setRawBrief(defaultRawBrief);
              setBriefDirty(true);
              setParserNotes([]);
              setStructuredBrief(null);
              setRetrievalPlan(null);
              setMetadata(null);
              setCandidates([]);
              setSelectedCandidate(null);
            }}
            onStructure={handleStructure}
          />
        </div>

        <div className="center-column">
          <TemplateSelector
            templates={templates}
            selectedTemplateId={selectedTemplateId}
            isBusy={isBusy}
            onTemplateChange={setSelectedTemplateId}
            onGeneratePlan={handleGeneratePlan}
            onRun={handleRun}
          />
          <RetrievalPlanPanel metadata={metadata} plan={retrievalPlan} />
          <CandidateTable candidates={candidates} onSelect={setSelectedCandidate} />
        </div>

        <div className="right-column">
          <CandidateDrawer candidate={selectedCandidate} onClose={() => setSelectedCandidate(null)} />
        </div>
      </main>
    </div>
  );
}
