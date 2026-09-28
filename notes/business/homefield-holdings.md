# Homefield Holdings

Homefield Holdings is our Amazon FBA business, run with the help of an online arbitrage (OA) engine.

## Where it lives
- Code, data, docs, and Dani's Stryker files and app: private GitHub repo `TxNathans/homefield-stryker`.
  - `homefield-holdings/` — OA engine, data, scheduled-task prompts, docs.
  - `stryker/` — Dani's Stryker files; `stryker/app/` — the app she built.
- Clone it next to this repo on each computer: `$HOME\homefield-stryker`.
- Run `git pull` before starting work; let Claude commit and push when done.

## What runs automatically (no computer needs to be on)
| Job | Where | When (Central) |
|-----|-------|----------------|
| OA Engine morning run | GitHub Actions | 5:30am daily |
| OA Engine nightly run | GitHub Actions | 9:00pm daily |
| fba-morning-brief | Claude cloud Routine | 7:00am weekdays |
| fba-weekly-review | Claude cloud Routine | 8:00am Sundays |
| fba-product-research | Claude cloud Routine | every 3 hours |

API keys are stored as GitHub repo secrets and in a local `.env`, never in either repo.

## Rules
- Keep Homefield and Stryker separate from Tucker's other work.
- The old PC (DESKTOP-PC2M881) is being retired. Its local scheduled tasks are to be disabled
  once the cloud jobs are confirmed working.
