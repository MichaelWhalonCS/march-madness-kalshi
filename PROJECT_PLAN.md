# March Madness Survivor Tool — Project Plan

## Overview

A static site published via **GitHub Pages** that shows NCAA March Madness odds from Kalshi prediction markets in a table optimized for survivor contest strategy. A Python script pulls odds from the Kalshi API, generates a self-contained `index.html`, and pushes it. No backend server needed.

**Target User:** Joel — needs the table ready by **Tue/Wed March 18-19, 2026** (before the first round tips). Only cares about surviving teams between rounds, not during live games.

---

## What It Does

```
Team               | Seed | Region | R64→R32 | R32→S16 | S16→E8 | E8→F4 | F4→Final | Champ | Best Pick
--------------------|------|--------|---------|---------|--------|-------|----------|-------|----------
Duke                |  1   | East   |   97%   |   82%   |  55%   |  35%  |   22%    |  12%  | R64 (97%)
NC A&T              | 16   | East   |    3%   |    1%   |   0%   |   0%  |    0%    |   0%  | —
Memphis             |  8   | East   |   52%   |   18%   |   6%   |   2%  |    1%    |   0%  | R64 (52%)
...
```

- Python script pulls March Madness markets from Kalshi API
- Maps each market → `(team, round)` pair → implied probability
- Generates a **static HTML file** with sortable, color-coded table
- Published to **GitHub Pages** — Joel just opens a URL
- Auto-refreshes daily at **12:05 AM CT** via GitHub Actions
- Historical snapshots saved as JSON files in `data/snapshots/`

---

## Architecture

```
march_madness_kalshi/              # GitHub repo: MichaelWhalonCS/march-madness-kalshi
├── .github/
│   └── workflows/
│       └── refresh.yml            # GitHub Actions: daily 12:05 AM CT → run script → commit → deploy
│
├── .env.example                   # Kalshi API creds template
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── README.md
├── PROJECT_PLAN.md
│
├── docs/                          # GitHub Pages source (served as static site)
│   └── index.html                 # Generated — THE deliverable (don't hand-edit)
│
├── data/
│   └── snapshots/                 # Historical odds snapshots (JSON, committed to repo)
│       ├── 2026-03-18T00-05.json
│       └── 2026-03-20T00-05.json
│
├── scripts/
│   ├── discover_tickers.py        # One-off: explore Kalshi API for NCAA market tickers
│   └── refresh.py                 # Main entry: pull odds → generate HTML → save snapshot
│
├── src/
│   ├── __init__.py
│   ├── config.py                  # Pydantic settings (Kalshi creds, paths)
│   ├── kalshi_client.py           # Kalshi client singleton (adapted from existing repo)
│   ├── odds.py                    # Fetch markets → parse → return structured odds
│   ├── teams.py                   # Tournament teams, seeds, regions, name normalization
│   └── html_gen.py                # Generate self-contained index.html (Jinja2)
│
├── templates/
│   └── table.html                 # Jinja2 template for the static page
│
└── tests/
    ├── __init__.py
    ├── test_odds.py
    └── test_html_gen.py
```

**Key simplification:** No FastAPI, no DuckDB, no Docker, no server process. Just:
1. Run `python scripts/refresh.py`
2. It generates `docs/index.html`
3. Push to GitHub → Pages auto-deploys
4. Joel opens the URL

---

## Implementation Plan (Ordered Steps)

### Phase 1 — Scaffold & Kalshi Client (Day 1)

| # | Task | Details |
|---|------|---------|
| 1 | **Create GitHub repo** | `march-madness-kalshi` under **MichaelWhalonCS**. Enable GitHub Pages from `docs/` folder on `main` branch. |
| 2 | **Project config** | `pyproject.toml`, `.gitignore` (ignore `.env`, `__pycache__`, `*.egg-info`), `.env.example`, `requirements.txt`. Minimal deps: `pykalshi[dataframe]`, `pydantic-settings`, `jinja2`, `structlog`. |
| 3 | **Config module** | Adapt `config.py` from existing repo. Just Kalshi creds + output paths. |
| 4 | **Kalshi client** | Adapt `services/kalshi.py` → `src/kalshi_client.py`. Same singleton pattern, same auth. |
| 5 | **Discover tickers script** | `scripts/discover_tickers.py` — search Kalshi for NCAA/March Madness events/series. Print all matching tickers and market titles. Run once, inspect, hardcode the relevant ones. |

### Phase 2 — Core Odds Logic (Day 1-2)

| # | Task | Details |
|---|------|---------|
| 6 | **Tournament structure** | `src/teams.py` — Hardcode 68 teams with seed, region. Map display names to Kalshi naming. Define rounds: R64, R32, S16, E8, F4, Championship. |
| 7 | **Odds fetcher** | `src/odds.py` — `fetch_odds() → list[TeamOdds]`. Calls Kalshi API, parses market titles to extract team + round, converts prices → implied probability (midpoint of yes_bid/yes_ask ÷ 100). |
| 8 | **Team name normalization** | Fuzzy/alias mapping in `teams.py`. Handle "Duke Blue Devils" vs "Duke", etc. |
| 9 | **Survivor helper logic** | For each team, calculate: (a) which round gives the best "use this team" value, (b) conditional advancement probabilities (P(win R32 game) = P(make S16) / P(make R32)). |

### Phase 3 — HTML Generation & Snapshots (Day 2)

| # | Task | Details |
|---|------|---------|
| 10 | **Jinja2 template** | `templates/table.html` — Self-contained HTML with inline CSS + JS. Sortable columns (click header). Color-coded probability cells (green→red gradient). Mobile-friendly. Shows "Last updated" timestamp. |
| 11 | **HTML generator** | `src/html_gen.py` — Takes `list[TeamOdds]`, renders template, writes to `docs/index.html`. |
| 12 | **Snapshot saving** | `scripts/refresh.py` saves a JSON snapshot to `data/snapshots/{timestamp}.json` each run. Simple archival — can diff odds over time by comparing JSON files. |

### Phase 4 — Automation & Polish (Day 2-3)

| # | Task | Details |
|---|------|---------|
| 13 | **`scripts/refresh.py`** | Main entry point. Loads config → fetches odds → generates HTML → saves snapshot. Run with `python scripts/refresh.py`. |
| 14 | **GitHub Actions workflow** | `.github/workflows/refresh.yml` — Runs daily at **12:05 AM CT (6:05 AM UTC)** via cron: `5 6 * * *`. Uses repo secrets for Kalshi API key + private key. Commits updated `docs/index.html` and snapshot, then pushes. Also allows manual trigger via `workflow_dispatch`. |
| 15 | **Handle eliminated teams** | After a round, manually update `teams.py` to mark eliminations (or auto-detect from settled Kalshi markets). Grayed out in table. |
| 16 | **README** | Setup: clone, `pip install`, add `.env`, run `python scripts/refresh.py`, open `docs/index.html`. GitHub Pages URL for Joel. |

---

## Key Design Decisions

1. **Static site via GitHub Pages.** No server to run or maintain. Joel gets a URL. We re-generate the HTML whenever we want fresh odds.

2. **No database.** JSON snapshots in `data/snapshots/` for history. Flat files are fine for this scale.

3. **Kalshi-only data source.** Kalshi prices = implied probabilities. No scraping.

4. **Midpoint pricing.** Implied probability = `(yes_bid + yes_ask) / 2 / 100`. Fallback to `last_price / 100` if no orderbook.

5. **Self-contained HTML.** The generated `index.html` has everything inline (CSS, JS, data). No external dependencies. Can be opened as a local file too.

6. **Daily auto-refresh at 12:05 AM CT.** Markets are stale during games anyway. Overnight refresh catches all settled results and updated lines. Can also trigger manually.

7. **Reuse pykalshi client pattern** from `prediction_market_analysis` repo — same auth, same singleton.

---

## Environment Variables

```env
KALSHI_API_KEY_ID=your-api-key-id
KALSHI_PRIVATE_KEY_PATH=/path/to/your/kalshi_private_key.pem
KALSHI_BASE_URL=https://api.kalshi.co
```

**GitHub Actions Secrets** (set in repo Settings → Secrets):
- `KALSHI_API_KEY_ID`
- `KALSHI_PRIVATE_KEY` (the actual key content, not a path — Actions writes it to a temp file)

---

## Dependencies

```
pykalshi[dataframe]>=0.1.0
pydantic>=2.6.0
pydantic-settings>=2.1.0
jinja2>=3.1.0
structlog>=24.1.0
```

Dev:
```
pytest>=8.0.0
ruff>=0.2.0
```

That's it. No FastAPI, no uvicorn, no DuckDB, no Docker.

---

## GitHub Pages Setup

1. Go to repo **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: `main`, folder: `/docs`
4. URL will be: `https://michaelwhaloncs.github.io/march-madness-kalshi/`

---

## GitHub Actions Cron Schedule

```yaml
on:
  schedule:
    - cron: '5 6 * * *'   # 6:05 AM UTC = 12:05 AM CT (UTC-6)
  workflow_dispatch:        # Manual trigger button in Actions tab
```

---

## Milestone Checklist

- [ ] Repo created on MichaelWhalonCS, GitHub Pages enabled
- [ ] Kalshi client connects, `discover_tickers.py` finds March Madness markets
- [ ] Odds parsing works — maps markets to (team, round) pairs
- [ ] `refresh.py` generates `docs/index.html` with full table
- [ ] Table is sortable, color-coded, shows survivor helper columns
- [ ] GitHub Pages live — Joel can open `https://michaelwhaloncs.github.io/march-madness-kalshi/`
- [ ] GitHub Actions daily refresh at 12:05 AM CT working
- [ ] README complete

---

## Open Questions (To Resolve During Phase 1)

1. **What are the exact Kalshi tickers for March Madness 2026?** Need to explore the API. Could be series like `MARCHMAD`, events like `NCAAT-2026-R64-DUKE-VSU`, etc.

2. **Does Kalshi have per-round advancement markets, or only game-level + champion?** This determines how we fill the table. If only game markets exist, we multiply conditional probabilities.

3. **Does Kalshi have "make the Sweet 16" style markets?** If yes, we can directly read advancement odds. If not, we derive from individual game lines.

4. **Team name format in Kalshi?** Run `discover_tickers.py` to see actual market titles.

---

## Timeline

| Day | Target |
|-----|--------|
| **Day 1** (Thu 3/13) | Phase 1: Scaffold repo, client, discover tickers |
| **Day 2** (Fri 3/14) | Phase 2-3: Odds logic, HTML table generation |
| **Day 3** (Sat-Mon 3/15-17) | Phase 4: Polish, GitHub Actions, README, ship |
| **Tue 3/18** | 🏀 First Four begins — table is live at GitHub Pages URL |
