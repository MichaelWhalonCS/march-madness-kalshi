# March Madness Survivor Tool

A static site that shows NCAA March Madness odds from [Kalshi](https://kalshi.com) prediction markets in a table optimized for survivor contest strategy.

**Live site:** [https://michaelwhaloncs.github.io/march-madness-kalshi/](https://michaelwhaloncs.github.io/march-madness-kalshi/)

## How It Works

1. A Python script pulls March Madness market odds from the Kalshi API
2. It generates a self-contained `docs/index.html` with a sortable, color-coded table
3. GitHub Pages serves it as a static site
4. GitHub Actions auto-refreshes daily at 12:05 AM CT

No backend server needed.

## Table Features

- **Per-round advancement probabilities** — R64→R32, R32→S16, S16→E8, E8→F4, F4→Final, Championship
- **Best Pick column** — which round to "use" each team in your survivor pool
- **Sortable columns** — click any header to sort
- **Color-coded cells** — green (high probability) → red (low probability)
- **Region/seed filters** — narrow down the view
- **Mobile-friendly** — works on phones

## Local Setup

```bash
# Clone
git clone https://github.com/MichaelWhalonCS/march-madness-kalshi.git
cd march-madness-kalshi

# Create virtual environment
python -m venv .venv
source .venv/Scripts/activate  # Windows
# source .venv/bin/activate    # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Add your Kalshi credentials
cp .env.example .env
# Edit .env with your API key and private key path

# Run the refresh script
python scripts/refresh.py

# Open the generated page
open docs/index.html
```

## Discovering Kalshi Markets

Before the first run, explore what March Madness markets exist on Kalshi:

```bash
python scripts/discover_tickers.py
```

Then update `src/odds.py` with the relevant series tickers and round keywords.

## Project Structure

```
├── .github/workflows/refresh.yml   # Daily auto-refresh via GitHub Actions
├── docs/index.html                  # Generated static page (GitHub Pages source)
├── data/snapshots/                  # Historical odds snapshots (JSON)
├── scripts/
│   ├── refresh.py                   # Main entry: pull odds → generate HTML
│   └── discover_tickers.py          # One-off: explore Kalshi API for tickers
├── src/
│   ├── config.py                    # Pydantic settings
│   ├── kalshi_client.py             # Kalshi API client singleton
│   ├── odds.py                      # Fetch + parse market odds
│   ├── teams.py                     # Tournament teams, seeds, regions
│   └── html_gen.py                  # Generate self-contained HTML
└── templates/table.html             # Jinja2 template for the page
```

## GitHub Actions Secrets

Set these in the repo's Settings → Secrets → Actions:

- `KALSHI_API_KEY_ID` — Your Kalshi API key ID
- `KALSHI_PRIVATE_KEY` — The full content of your private key PEM file

## Timeline

- **Selection Sunday (March 15)** — Bracket announced, teams filled in
- **Sunday/Monday (March 15-16)** — Kalshi markets go live, tickers configured
- **Tuesday (March 18)** — First Four begins, table is live
