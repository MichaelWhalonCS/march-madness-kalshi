# March Madness Kalshi Survivor Tool — Chat Context

Use this as the opening message when starting a new Copilot chat session for this project.

---

## Paste the below into a new chat:

---

I'm working on a **March Madness survivor pool tool** powered by Kalshi prediction markets, deployed to GitHub Pages. Here's the full project context:

### Project Overview
- **Repo:** `MichaelWhalonCS/march-madness-kalshi` (public, `master` branch; default branch is `main`)
- **Live site:** https://michaelwhaloncs.github.io/march-madness-kalshi/
- **Workspace:** `c:\Users\Michael\Desktop\projects\march_madness_kalshi`
- **Python 3.12.1**, venv at `.venv/` (activate: `source .venv/Scripts/activate` in Git Bash)
- **Key deps:** pykalshi 0.4.0, pydantic-settings, jinja2, structlog, pytest, ruff

### What It Does
A Python script (`scripts/refresh.py`) pulls March Madness odds entirely from Kalshi prediction markets, generates a self-contained `docs/index.html` with sortable/filterable tables, and deploys via GitHub Pages. No backend server.

The page has three sections:
1. **Main odds table** — per-team probabilities for each round (R64 through Championship), color-coded, with filters (Region, Seed, Search, Day, Show Eliminated)
2. **Suggested pick series** — beam-search optimizer showing top 3 survivor pick sequences
3. **Future Value table** — ranks teams by whether to use them now vs. save for a later round (`FV = %win_current - Σ(2^i × %future_round_i)`)

### Data Sources (All Kalshi)
- **Per-game markets** (`KXNCAAMBGAME` series): Binary win markets for each game. ~64 active, ~900+ finalized. Prices are dollars (0.00–1.00); we take midpoint of yes_bid/yes_ask.
- **Tournament futures** (`KXMARMADROUND` series): Per-team advancement to each round. Events map as: `26RO32→R64`, `26S16→R32`, `26E8→S16`, `26F4→E8`, `26T2→F4`
- **Championship** (`KXMARMAD-26` event): Win-it-all market

### Architecture
```
src/
├── config.py          — Pydantic settings (current_round="R64", Kalshi creds, paths)
├── kalshi_client.py   — pykalshi singleton client
├── odds.py (628 lines) — All data fetching, TeamOdds dataclass, price_to_prob(), _parse_ticker(), _fetch_kalshi_probs(), _fetch_kalshi_futures(), fetch_odds(), best_survivor_series()
├── teams.py (223 lines) — 68 teams with seed/region/kalshi_abbr, KALSHI_ABBR_MAP, ROUNDS, ROUND_LABELS, find_team()
└── html_gen.py (316 lines) — _prob_display (1 decimal %), _prob_color, _compute_future_value(), generate_html()

templates/table.html (1013 lines) — Jinja2 template: dark theme, sortable columns, day filter, FV table
scripts/refresh.py — Entry point: fetch_odds → generate_html → save_snapshot
tests/ — test_odds.py (99 lines), test_html_gen.py (110 lines) — 23 tests total, all passing
```

### Key Technical Details
- **pykalshi 0.4.0**: Returns `DataFrameList[Market]` objects. `Market` wraps Pydantic `MarketModel` in `.data`. Use `market.data.model_dump()` to get dict.
- **Ticker format**: `KXNCAAMBGAME-26MAR19SIEDUKE-DUKE` (series-dateMatchup-teamAbbr)
- **Futures ticker format**: `KXMARMADROUND-26RO32-DUKE`
- **Closed market filtering**: `_CLOSED_STATUSES = {"finalized", "settled", "closed", "determined"}`
- **Day-of-week column**: Shows for R64/R32 rounds. `_DATE_TO_DAY` maps dates to weekday abbreviations.
- **FV formula**: `Weighted FV = %win_next_rd - (1×%make_16 + 2×%make_8 + 4×%make_4 + 8×%make_final + 16×%win_champ)` — green=use now, blue=save

### CI/CD
- **GitHub Actions**: `.github/workflows/refresh.yml`
- **Schedule**: Cron at 6:05 AM UTC (12:05 AM CT) + manual `workflow_dispatch`
- **Secrets** (configured and working): `KALSHI_API_KEY_ID` and `KALSHI_PRIVATE_KEY`
- **Kalshi API Key ID**: `6aa46fcc-a900-4f2d-8c6f-97bdeb580d9e`
- **Private key path**: `secrets/kalshi_private_key.pem` (gitignored)

### Known Data Quirks
- 4 teams sometimes missing per-game markets (First Four / TBD matchups): BYU, Florida, Michigan, Tennessee
- 8 First Four teams (Mar 17–18) show large per-game vs. R64 futures gap — expected (per-game = play-in only, futures = play-in + R64)
- ~13 minor monotonicity violations in thin/illiquid longshot markets (1–6% prob range) — noise, not bugs

### Recent Git History
```
0700f97 (HEAD) Add Future Value table for survivor pick optimization
886ff8f Add day-of-week column and filter for R64/R32 games
23c10b6 Add tenths place to all percentage displays
be7daae Replace ESPN BPI with Kalshi tournament futures
f5571dc refresh: populate Kalshi odds (CI was missing API creds)
```

### Last Known Issue
User reported "Duke's Kalshi R64 odds are clearly off" — not yet investigated. Snapshot data showed Duke Kalshi per-game=99.5%, R64 futures=0.995, R32=0.855, S16=0.675, Champ=0.195. May be a display issue, stale market, or external comparison mismatch. Start here if continuing bug investigation.

### Environment
- Windows, Git Bash terminal
- `.env` file has: `KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH=secrets/kalshi_private_key.pem`, `KALSHI_BASE_URL=https://api.elections.kalshi.com/trade-api/v2`
