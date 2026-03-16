"""Fetch March Madness odds from Kalshi and structure them for the table.

Kalshi has per-game win markets under the KXNCAAMBGAME series.
Each game has two markets (one per team), e.g.:
  KXNCAAMBGAME-26MAR19SIEDUKE-DUKE  → "Siena at Duke Winner?"
  KXNCAAMBGAME-26MAR19SIEDUKE-SIE   → "Siena at Duke Winner?"

Market prices are in dollars (0.00–1.00).  We take the midpoint of
yes_bid_dollars / yes_ask_dollars as the implied probability.

Only the current round's games are available at any time — we map each
team's game-win probability to its current round's cumulative probability.
"""

from __future__ import annotations

import random
import structlog
from dataclasses import dataclass, field

from .kalshi_client import get_client
from .teams import Team, find_team, get_all_teams, ROUNDS, KALSHI_ABBR_MAP
from .config import settings

logger = structlog.get_logger()


# ── Market configuration ───────────────────────────────────────────────────────

SERIES_TICKER = "KXNCAAMBGAME"

# Dates → round mapping.  Kalshi tickers embed the date like "26MAR19".
# First Four: March 17–18;  R64: March 19–20;  R32: March 21–22;
# S16: March 26–27;  E8: March 28–29;  F4: April 4;  Championship: April 6
_DATE_TO_ROUND: dict[str, str] = {
    "MAR17": "R64",   # First Four (counts as R64 for survivor)
    "MAR18": "R64",   # First Four
    "MAR19": "R64",
    "MAR20": "R64",
    "MAR21": "R32",
    "MAR22": "R32",
    "MAR26": "S16",
    "MAR27": "S16",
    "MAR28": "E8",
    "MAR29": "E8",
    "APR04": "F4",
    "APR06": "Championship",
}


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class TeamOdds:
    """Odds for a single team across all rounds."""

    team: Team
    round_probs: dict[str, float | None] = field(default_factory=dict)
    # round_probs maps round code → implied probability (0.0–1.0), None if no market

    # Kalshi per-game market probability for the current round (None if no market)
    kalshi_prob: float | None = None
    # Direct link to this team's Kalshi market page (None if no market)
    kalshi_url: str | None = None

    # Minimum conditional win probability to consider a round "safe" for survivor
    SAFE_THRESHOLD: float = 0.70

    def conditional_probs(self) -> dict[str, float | None]:
        """Conditional win probability for each round's game.

        P(win R64 game) = P(make R32) = round_probs["R64"]
        P(win R32 game) = P(make S16) / P(make R32)
        etc.
        """
        result: dict[str, float | None] = {}
        for i, rnd in enumerate(ROUNDS):
            if rnd == "R64":
                # R64 prob IS the conditional — it's the first game
                result[rnd] = self.round_probs.get(rnd)
            else:
                prev_rnd = ROUNDS[i - 1]
                prev = self.round_probs.get(prev_rnd)
                curr = self.round_probs.get(rnd)
                if prev and prev > 0 and curr is not None:
                    result[rnd] = curr / prev
                else:
                    result[rnd] = None
        return result

    @property
    def best_pick_round(self) -> str | None:
        """Latest round where this team's conditional win rate is >= SAFE_THRESHOLD.

        Survivor strategy: save strong teams for the latest round where they
        still have a high chance of winning their game. Don't waste a 1-seed
        on R64 when they're also 75% to win their R32 game.

        Falls back to the round with the highest conditional probability if
        no round meets the threshold.
        """
        conds = self.conditional_probs()
        # Find latest round above threshold (iterate in reverse)
        for rnd in reversed(ROUNDS):
            prob = conds.get(rnd)
            if prob is not None and prob >= self.SAFE_THRESHOLD:
                return rnd

        # Fallback: highest conditional prob
        best_round = None
        best_prob = -1.0
        for rnd, prob in conds.items():
            if prob is not None and prob > best_prob:
                best_prob = prob
                best_round = rnd
        return best_round

    @property
    def best_pick_prob(self) -> float | None:
        """Conditional win probability for the best pick round."""
        rnd = self.best_pick_round
        if rnd is None:
            return None
        return self.conditional_probs().get(rnd)

    def conditional_prob(self, round_code: str) -> float | None:
        """P(win this round's game). Convenience wrapper around conditional_probs()."""
        return self.conditional_probs().get(round_code)


# ── Price → probability ────────────────────────────────────────────────────────

def price_to_prob(market: dict) -> float:
    """Convert Kalshi market prices to implied probability.

    Strategy: midpoint of yes_bid / yes_ask. Fallback to last_price.
    Kalshi prices are in dollars (0.00–1.00).
    """
    # New API uses dollar-denominated fields
    yes_bid = market.get("yes_bid_dollars") or market.get("yes_bid")
    yes_ask = market.get("yes_ask_dollars") or market.get("yes_ask")

    # Dollar prices are 0.00–1.00 already
    if yes_bid is not None and yes_ask is not None:
        bid = float(yes_bid)
        ask = float(yes_ask)
        if bid > 0 and ask > 0:
            # If values look like cents (>1), divide by 100
            if bid > 1 or ask > 1:
                return (bid + ask) / 2 / 100
            return (bid + ask) / 2

    last_price = market.get("last_price_dollars") or market.get("last_price", 0)
    if last_price:
        lp = float(last_price)
        if lp > 0:
            return lp / 100 if lp > 1 else lp

    return 0.0


# ── Market parsing ─────────────────────────────────────────────────────────────

def _parse_ticker(ticker: str) -> tuple[str | None, str | None]:
    """Extract (kalshi_abbr, round_code) from a Kalshi market ticker.

    Ticker format: KXNCAAMBGAME-26MAR19SIEDUKE-DUKE
                   ^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^  ^^^^
                   series        date+matchup      team abbr

    Returns (team_kalshi_abbr, round_code) or (None, None).
    """
    parts = ticker.split("-")
    if len(parts) < 3 or parts[0] != SERIES_TICKER:
        return None, None

    team_abbr = parts[-1]  # Last segment is the team abbreviation
    game_part = parts[1]   # e.g. "26MAR19SIEDUKE"

    # Extract date: first 7 chars = "26MAR19" → take chars 2..7 = "MAR19"
    if len(game_part) < 7:
        return None, None
    date_str = game_part[2:7]  # e.g. "MAR19"

    round_code = _DATE_TO_ROUND.get(date_str)
    return team_abbr, round_code


# ── Main fetch function ────────────────────────────────────────────────────────

# Kalshi market page URL pattern:
# https://kalshi.com/markets/kxncaambgame/{event_ticker_lowercase}
_KALSHI_MARKET_URL_BASE = "https://kalshi.com/markets/kxncaambgame"


def _fetch_kalshi_probs() -> tuple[dict[str, float], dict[str, str]]:
    """Fetch current-round Kalshi market probabilities, keyed by team name.

    Returns:
        (probs, urls) where:
            probs: dict team_name → implied probability (0.0–1.0)
            urls:  dict team_name → Kalshi market page URL
        Both empty if Kalshi API is unreachable or has no markets.
    """
    try:
        client = get_client()
        markets = client.get_markets(series_ticker=SERIES_TICKER, limit=1000)
        if isinstance(markets, dict):
            markets = markets.get("markets", [])
        # pykalshi 0.4.0 may return a DataFrameList; coerce to list of dicts
        if hasattr(markets, "to_dicts"):
            markets = markets.to_dicts()
    except Exception:
        logger.warning("Could not fetch Kalshi markets — continuing with ESPN BPI only")
        return {}, {}

    probs: dict[str, float] = {}
    urls: dict[str, str] = {}
    for market in markets:
        # Handle both dict and object-style access
        ticker = market.get("ticker", "") if isinstance(market, dict) else getattr(market, "ticker", "")
        event_ticker = market.get("event_ticker", "") if isinstance(market, dict) else getattr(market, "event_ticker", "")
        team_abbr, round_code = _parse_ticker(ticker)
        if not team_abbr:
            continue

        team_obj = KALSHI_ABBR_MAP.get(team_abbr)
        if not team_obj:
            continue

        prob = price_to_prob(market if isinstance(market, dict) else market.__dict__)
        if prob > 0:
            probs[team_obj.name] = prob
            if event_ticker:
                urls[team_obj.name] = f"{_KALSHI_MARKET_URL_BASE}/{event_ticker.lower()}"
            logger.debug("Kalshi market", team=team_obj.name, prob=f"{prob:.1%}", ticker=ticker)

    logger.info("Kalshi markets fetched", parsed=len(probs))
    return probs, urls


def fetch_odds() -> list[TeamOdds]:
    """Fetch odds from ESPN BPI (all rounds) + Kalshi (current round).

    ESPN BPI provides cumulative advancement probabilities for all rounds.
    Kalshi provides per-game win probabilities for the current round only.
    Both are included so the user can compare model-based and market-based odds.
    """
    from .espn_bpi import fetch_bpi

    # 1. ESPN BPI — multi-round advancement probabilities
    bpi_data = fetch_bpi()  # dict: team_name → {round_code → prob}

    if not bpi_data:
        logger.warning("No ESPN BPI data — falling back to sample odds")
        return _generate_sample_odds()

    # 2. Kalshi — current-round per-game market prices
    kalshi_probs, kalshi_urls = _fetch_kalshi_probs()  # dicts: team_name → prob / url

    # 3. Build TeamOdds for every team
    result: list[TeamOdds] = []
    for team in get_all_teams():
        round_probs = bpi_data.get(team.name, {})
        kalshi_prob = kalshi_probs.get(team.name)
        kalshi_url = kalshi_urls.get(team.name)

        result.append(TeamOdds(
            team=team,
            round_probs=round_probs,
            kalshi_prob=kalshi_prob,
            kalshi_url=kalshi_url,
        ))

    teams_with_bpi = sum(1 for to in result if to.round_probs)
    teams_with_kalshi = sum(1 for to in result if to.kalshi_prob is not None)
    logger.info(
        "Odds assembled",
        total_teams=len(result),
        with_bpi=teams_with_bpi,
        with_kalshi=teams_with_kalshi,
    )
    return result


def _empty_odds() -> list[TeamOdds]:
    """Return TeamOdds with no probabilities for all teams (placeholder)."""
    return [TeamOdds(team=team) for team in get_all_teams()]


# ── Sample data generation ─────────────────────────────────────────────────────

# Base R64 win probability by seed (historical averages, slightly noisy)
_SEED_BASE_R64: dict[int, float] = {
    1: 0.97, 2: 0.93, 3: 0.85, 4: 0.80,
    5: 0.66, 6: 0.63, 7: 0.61, 8: 0.52,
    9: 0.48, 10: 0.39, 11: 0.37, 12: 0.34,
    13: 0.20, 14: 0.15, 15: 0.07, 16: 0.02,
}

# Approximate conditional win rate per round (given you made it there)
_ROUND_DECAY: dict[str, float] = {
    "R64": 1.0,     # base probability
    "R32": 0.78,    # P(win R32 | made R32) for a strong team
    "S16": 0.65,
    "E8": 0.55,
    "F4": 0.48,
    "Championship": 0.45,
}


def _generate_sample_odds() -> list[TeamOdds]:
    """Generate realistic sample odds based on seed for all teams.

    Uses historical seed-based win rates with some randomness added
    so the table looks realistic for development/testing.
    """
    random.seed(2026)  # Deterministic for consistent output
    result = []

    for team in get_all_teams():
        base = _SEED_BASE_R64.get(team.seed, 0.10)
        # Add some team-specific noise (±5% for top seeds, ±10% for lower)
        noise_scale = 0.05 if team.seed <= 4 else 0.10
        base = max(0.01, min(0.99, base + random.uniform(-noise_scale, noise_scale)))

        probs: dict[str, float] = {}
        cumulative = base

        for rnd in ROUNDS:
            if rnd == "R64":
                probs[rnd] = round(cumulative, 3)
            else:
                # Each round: multiply by decay factor (adjusted by seed strength)
                seed_factor = max(0.3, 1.0 - (team.seed - 1) * 0.04)
                decay = _ROUND_DECAY[rnd] * seed_factor
                # Add noise
                decay = max(0.15, min(0.95, decay + random.uniform(-0.08, 0.08)))
                cumulative *= decay
                if cumulative < 0.002:
                    cumulative = 0.0
                probs[rnd] = round(cumulative, 3)

        result.append(TeamOdds(team=team, round_probs=probs))

    logger.info("Generated sample odds", teams=len(result))
    return result


def odds_to_snapshot(odds: list[TeamOdds]) -> list[dict]:
    """Convert TeamOdds list to a JSON-serializable snapshot format."""
    snapshot = []
    for to in odds:
        snapshot.append({
            "team": to.team.name,
            "seed": to.team.seed,
            "region": to.team.region,
            "eliminated": to.team.eliminated,
            "round_probs": {
                rnd: prob for rnd, prob in to.round_probs.items()
            },
            "kalshi_prob": to.kalshi_prob,
            "kalshi_url": to.kalshi_url,
            "best_pick_round": to.best_pick_round,
            "best_pick_prob": to.best_pick_prob,
        })
    return snapshot
