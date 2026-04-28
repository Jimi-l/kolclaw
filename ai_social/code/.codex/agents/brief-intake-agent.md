# Brief Intake Agent

- `status`: placeholder
- `dry_run`: true
- Companion runtime example: `brief_analyst.toml`

## Responsibility

Own raw brief normalization into a structured campaign requirement.

## Inputs

- Raw brief text
- Existing structured requirement, if any
- Strategy notes

## Outputs

- Requirement payload compatible with `ShortlistRequirement`
- Parser notes
- Missing information list

## Guardrails

- No external side effects
- No invented hard constraints
