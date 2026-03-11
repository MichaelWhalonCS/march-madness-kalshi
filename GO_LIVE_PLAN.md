# Go-Live Plan: Real Teams & Kalshi Odds

Once the bracket is announced (Selection Sunday) and Kalshi markets go live, follow these steps in order.

---

## Phase 1: Selection Sunday — Fill the Bracket (March 15)

### 1. Update `src/teams.py` — TEAMS list
Replace all 64 placeholder teams with the actual bracket.

```python
TEAMS: list[Team] = [
    # ── East Region ────
    Team("Duke", 1, "East"),   # ← real team, real seed, real region
    Team("Auburn", 2, "East"),
    # ... all 64
]
```

**What to check:**
- 4 regions × 16 seeds = 64 teams (no duplicates)
- Seed numbers 1–16 per region
- Names should be short display names (e.g. "UConn" not "University of Connecticut")

### 2. Update `src/teams.py` — ALIASES dict
If any team has a common alternate name, add it:
```python
ALIASES = {
    "connecticut": "UConn",
    "unc": "North Carolina",
    # etc.
}
```
This is used to match Kalshi market titles to our team names. Add aliases after running `discover_tickers.py` (Phase 2).

---

## Phase 2: Markets Go Live — Connect Kalshi (Sunday night / Monday)

### 1. Run `scripts/discover_tickers.py`
```bash
python scripts/discover_tickers.py
```
This searches Kalshi for NCAA tournament markets and prints:
- **Series tickers** (e.g. `"MARCHMAD"`, `"NCAAT-2026"`)
- **Event tickers** and **market tickers** with titles
- How teams are named in Kalshi titles

Save this output — you'll need it for the next steps.

### 2. Update `src/odds.py` — SERIES_TICKERS
Add the series/event tickers you found:
```python
SERIES_TICKERS: list[str] = [
    "MARCHMAD",     # ← whatever discover_tickers.py found
    # "NCAAT-2026",
]
```
This is what `fetch_odds()` uses to pull markets from the Kalshi API.

### 3. Update `src/odds.py` — ROUND_KEYWORDS
Map the keywords found in Kalshi market titles to our round codes:
```python
ROUND_KEYWORDS: dict[str, str] = {
    "round of 64": "R64",
    "round of 32": "R32",
    "sweet 16": "S16",
    "sweet sixteen": "S16",
    "elite 8": "E8",
    "elite eight": "E8",
    "final four": "F4",
    "championship": "Championship",
    "win the tournament": "Championship",
    "national champion": "Championship",
}
```
Look at the actual market titles from discover_tickers output and match the phrasing exactly.

### 4. Update `src/odds.py` — `_parse_team_round()` (if needed)
The current parser checks if a team name appears in the market title. If Kalshi uses a different format (e.g. team name in a `subtitle` field, or encoded in the ticker like `NCAAT-DUKE-R64`), update the parsing logic.

### 5. Update `src/teams.py` — ALIASES (round 2)
After seeing how Kalshi spells team names in their market titles, add any that don't match our display names:
```python
ALIASES = {
    "mississippi state bulldogs": "Mississippi St.",
    "brigham young cougars": "BYU",
    # etc.
}
```

### 6. Test the full pipeline
```bash
python scripts/refresh.py
```
- Check terminal output for "Skipped market" warnings — those are markets the parser couldn't match
- Open `docs/index.html` in browser and verify all 64 teams have probability data
- If some teams show "—" for all rounds, their Kalshi name isn't matching — add an alias

### 7. Push and verify GitHub Pages
```bash
git add -A
git commit -m "Go live: real bracket + Kalshi market data"
git push
```
Wait ~1 min, then check https://michaelwhaloncs.github.io/march-madness-kalshi/

---

## Phase 3: During the Tournament — Round-by-Round Updates

### After each round completes:

#### 1. Update `CURRENT_ROUND` in `.env`
```dotenv
# R64 → R32 → S16 → E8 → F4 → Championship
CURRENT_ROUND=R32
```
This controls:
- Which columns are visible (completed rounds are hidden)
- The "Win & Out" column label and calculation

#### 2. Mark eliminated teams in `src/teams.py`
```python
Team("Vermont", 13, "South", eliminated=True),
```
Eliminated teams are hidden by default (toggle "Show eliminated" to reveal them).

#### 3. Re-run refresh
```bash
python scripts/refresh.py
git add -A
git commit -m "Update: R32 complete, advance to S16"
git push
```

#### 4. (Optional) Update the GitHub Actions workflow `.env` for `CURRENT_ROUND`
If using the daily auto-refresh, add the round to the workflow's `.env` creation step:

In `.github/workflows/refresh.yml`, update:
```yaml
      - name: Create .env file
        run: |
          echo "KALSHI_API_KEY_ID=${{ secrets.KALSHI_API_KEY_ID }}" > .env
          echo "KALSHI_PRIVATE_KEY_PATH=secrets/kalshi_private_key.pem" >> .env
          echo "KALSHI_BASE_URL=https://api.kalshi.co" >> .env
          echo "CURRENT_ROUND=R32" >> .env
```
Or store `CURRENT_ROUND` as a GitHub repo variable and reference it with `${{ vars.CURRENT_ROUND }}`.

---

## Round-by-Round Checklist

| Round complete | Set `CURRENT_ROUND` to | Visible columns start at | Win & Out label |
|---|---|---|---|
| *(start)* | `R64` | Make R32 | Win R32 & Out |
| R64 done | `R32` | Make S16 | Win S16 & Out |
| R32 done | `S16` | Make E8 | Win E8 & Out |
| S16 done | `E8` | Make F4 | Win F4 & Out |
| E8 done | `F4` | Make Final | Win Final & Out |
| F4 done | `Championship` | Win Title | *(just Win Title)* |

---

## File Change Summary

| File | What to change | When |
|---|---|---|
| `src/teams.py` — `TEAMS` | Replace 64 placeholder teams with real bracket | Selection Sunday |
| `src/teams.py` — `ALIASES` | Add Kalshi name → display name mappings | After discover_tickers |
| `src/teams.py` — `TEAMS` | Set `eliminated=True` on knocked-out teams | After each round |
| `src/odds.py` — `SERIES_TICKERS` | Add Kalshi series tickers | When markets go live |
| `src/odds.py` — `ROUND_KEYWORDS` | Map market title keywords to round codes | When markets go live |
| `src/odds.py` — `_parse_team_round()` | Adapt if Kalshi uses unexpected format | If needed |
| `.env` — `CURRENT_ROUND` | Advance to next round code | After each round completes |
| `.github/workflows/refresh.yml` | Update `CURRENT_ROUND` in .env step | After each round (for auto-refresh) |

---

## Troubleshooting

**"No series tickers configured — using sample odds data"**
→ `SERIES_TICKERS` in `src/odds.py` is still empty. Fill it with tickers from `discover_tickers.py`.

**Team shows "—" for all round probabilities**
→ Kalshi spells the team name differently. Run `discover_tickers.py`, find their spelling, add it to `ALIASES`.

**"Skipped market" warnings in refresh output**
→ The parser couldn't match a market to a team+round. Check the title logged and update `ROUND_KEYWORDS` or `ALIASES`.

**Odds look stale / not updating**
→ Kalshi markets may have low volume. The `price_to_prob()` function uses mid(bid, ask) with last_price fallback — if both are 0, the market has no activity.
