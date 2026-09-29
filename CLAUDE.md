# Context for Claude

This repo is Tucker and Dani's shared home base. It holds notes and background about our
household and the business we're building, so Claude has the same context on every computer.

## Who we are
- Tucker and Dani.
- We're building a business. (Add: what it is, stage, customers, goals.)

## How to help us
- Read the relevant files in `notes/` before answering questions about our home or business.
- When we share new facts worth keeping, offer to add them to the right file in `notes/`.
- Never write passwords, full account numbers, SSNs, or API keys into this repo.

## Where things live
- `notes/business/` — business plan, customers, vendors, pricing, decisions.
- `notes/home/` — house, maintenance, utilities, insurance.
- `notes/personal/` — family, important dates, plans.
- `notes/personal/health/` — WHOOP and Apple Health data. For "how did I sleep", `git pull` then read `whoop/sleep-log.md` and `apple/sleep.csv`. Setup and how it updates: `notes/personal/health/README.md`.
- `claude-export/` — backup of our claude.ai account data (Settings → Privacy → Export data).
- **Homefield Holdings** (the FBA / OA engine) and **Dani's Stryker files and app** live in the
  private repo `TxNathans/homefield-stryker`, cloned next to this repo (`$HOME\homefield-stryker`).
  Start Claude Code sessions as Local in that folder to work on them. Its scheduled jobs run in
  GitHub Actions and Claude cloud Routines, so no computer needs to be on. Keep Homefield and
  Stryker separate from Tucker's other work. See `notes/business/homefield-holdings.md`.
