# KOLClaw

**Project Status:** `legacy snapshot`

这个目录来自 `/home/tuo/code` 的只读导入快照，仅用于保留旧版实现与文档上下文，不再作为当前主运行目录继续开发。

KOLClaw is a first-pass scaffold for a brief-driven candidate generation engine.

This version is intentionally mock-first:

- It uses local JSON files instead of real platform data.
- It does not implement scraping, anti-bot logic, login automation, browser stealth, or account operations.
- It focuses on the core demo loop:
  `brief + strategy template -> retrieval plan -> candidate ranking`

## What It Does

- Structures a campaign brief from raw text or validates a structured brief.
- Loads reusable creator-selection strategy templates from local JSON.
- Builds a retrieval plan with selected filters, generated keywords, and ranking priorities.
- Loads mock creator candidates from local JSON.
- Applies hard filters first, then rule-based soft scoring.
- Returns explainable ranked candidates through a FastAPI API.
- Presents the result in a minimal React + Vite demo UI.

## Project Structure

```text
.
├── apps
│   ├── api
│   │   ├── app
│   │   │   ├── api
│   │   │   ├── core
│   │   │   ├── schemas
│   │   │   ├── services
│   │   │   └── utils
│   │   ├── main.py
│   │   └── requirements.txt
│   └── web
│       ├── src
│       │   ├── components
│       │   ├── lib
│       │   ├── pages
│       │   └── styles
│       ├── index.html
│       ├── package.json
│       ├── tsconfig.json
│       └── vite.config.ts
├── configs
│   └── strategy_templates
├── data
│   ├── mock_briefs
│   └── mock_candidates
├── docs
├── packages
│   └── shared
│       └── schemas
└── README.md
```

## Backend

### Requirements

- Python 3.11

### Install

```bash
cd /home/tuo/project/legacy/code_snapshot
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt
```

### Run

```bash
cd /home/tuo/project/legacy/code_snapshot/apps/api
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

### API Endpoints

- `GET /api/health`
- `GET /api/templates`
- `POST /api/brief/structure`
- `POST /api/retrieval/plan`
- `POST /api/candidates/run`
- `GET /api/candidates/sample`

## Frontend

### Requirements

- Node.js 20+ recommended

### Install

```bash
cd /home/tuo/project/legacy/code_snapshot/apps/web
npm install
```

### Run

```bash
cd /home/tuo/project/legacy/code_snapshot/apps/web
npm run dev
```

The demo UI will be available at `http://127.0.0.1:5173`.

The Vite dev server proxies `/api/*` to `http://127.0.0.1:8000`.

## Mock Data Included

- `configs/strategy_templates/fashion_event_default.json`
- `data/mock_briefs/fashion_offline_event.json`
- `data/mock_candidates/fashion_event_candidates.json`

The mock brief models a Shanghai offline fashion-show campaign on Douyin with a total budget of `132000`.

The mock candidate dataset contains 20 creators across:

- fashion
- beauty
- lifestyle
- dance
- pets
- parenting
- anime

Only a subset is expected to survive the configured hard filters.

## Scoring Model

Hard filters:

- platform match
- fans threshold
- female ratio threshold
- budget affordability
- creator type overlap

Soft scoring dimensions:

- `brief_match`
- `content_fit`
- `audience_fit`
- `commercial_efficiency`
- `growth_signal`

Default weighted formula:

```text
final_score =
  0.30 * brief_match +
  0.20 * content_fit +
  0.20 * commercial_efficiency +
  0.15 * audience_fit +
  0.15 * growth_signal
```

Weights are configurable per strategy template.

## Current Limitations

- No database
- No auth
- No background jobs
- No real platform adapters
- No external LLM or NLP service
- Raw brief structuring is a deterministic stub parser
- Scoring is rule-based, not learned or calibrated against production outcomes

## Future Extension Points

- Replace `brief_structurer.py` with a stronger parser or model-driven extraction pipeline.
- Replace `candidate_repository.py` with a real Xingtu or platform adapter.
- Add retrieval expansion adapters for Douyin, Xingtu, OCR, or media analysis.
- Add richer template versioning and multiple brand-specific strategies.
- Add persistence, review workflow, export, and collaboration features.
- Add offline evaluation data to tune score weights and thresholds.

## Notes

- Shared example payloads live under `packages/shared/schemas`.
- A short architecture overview is available in `docs/architecture.md`.
