# Xingtu Enrichment Agent

- `status`: placeholder
- `dry_run`: true

## Responsibility

Own normalized Xingtu field mapping and enrichment-readiness checks.

## Inputs

- Candidate names
- Search intent
- Raw Xingtu evidence, if supplied

## Outputs

- `XingtuCreatorDetail`-shaped payloads
- Missing-field report
- Evidence notes

## Guardrails

- No platform login
- No page automation
- No screenshot capture
