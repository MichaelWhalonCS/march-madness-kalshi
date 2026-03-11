"""Fetch March Madness odds from Kalshi and structure them for the table.

This module calls the Kalshi API, maps markets to (team, round) pairs,
and returns structured odds data ready for HTML generation.

When SERIES_TICKERS is empty (markets not yet live), generates realistic
sample odds based on seed so the full pipeline works end-to-end.

⚠️  MARKET_TICKERS needs to be populated once the markets go live on Kalshi
    (expected Sunday night / Monday, March 15-16, 2026).
"""

from __future__ import annotations

import random
import structlog
from dataclasses import dataclass, field

from .kalshi_client import get_client
from .teams import Team, find_team, get_all_teams, ROUNDS

logger = structlog.get_logger()


# ── Market configuration ───────────────────────────────────────────────────────
# How Kalshi structures March Madness markets determines how we fetch odds.
#
# Possible structures (to be confirmed via discover_tickers.py):
# 1. Per-round advancement: "Will Duke make the Sweet 16?" → direct probability
# 2. Per-game win: "Will Duke beat Vermont in R64?" → need to chain for advancement
# 3. Championship only: "Will Duke win the tournament?" → only one column
#
# We'll map Kalshi event/series tickers here once we see them.

# ⚠️  PLACEHOLDER — Fill after running discover_tickers.py
# Format: series_ticker or event_ticker prefix that we search for
SERIES_TICKERS: list[str] = [
    # e.g. "MARCHMAD", "NCAA-2026", "NCAAT"
    # Will be filled Sunday/Monday when markets go live
]

# If markets are per-team-per-round, map round keywords in market titles
ROUND_KEYWORDS: dict[str, str] = {
    # Kalshi market title fragment → our round code
    # e.g.:
    # "round of 64": "R64",
    # "round of 32": "R32",
    # "sweet 16": "S16",
    # "sweet sixteen": "S16",
    # "elite 8": "E8",
    # "elite eight": "E8",
    # "final four": "F4",
    # "championship": "Championship",
    # "win the tournament": "Championship",
    # "national champion": "Championship",
}


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class TeamOdds:
    """Odds for a single team across all rounds."""

    team: Team
    round_probs: dict[str, float | None] = field(default_factory=dict)
    # round_probs maps round code → implied probability (0.0–1.0), None if no market

    @property
    def best_pick_round(self) -> str | None:
        """The round where this team has the highest advancement probability.

        For survivor strategy: you want to "use" a team in the round where they're
        most likely to advance but still need to be used wisely (high probability
        means safe, but you might want to save them for a later round).
        """
        best_round = None
        best_prob = -1.0
        for rnd, prob in self.round_probs.items():
            if prob is not None and prob > best_prob:
                best_prob = prob
                best_round = rnd
        return best_round

    @property
    def best_pick_prob(self) -> float | None:
        """Probability for the best pick round."""
        rnd = self.best_pick_round
        return self.round_probs.get(rnd) if rnd else None

    def conditional_prob(self, round_code: str) -> float | None:
        """P(win this round's game) = P(make next round) / P(make this round).

        For example, P(win R32 game) = P(make S16) / P(make R32).
        This is the conditional advancement probability, useful for survivor strategy.
        """
        idx = ROUNDS.index(round_code) if round_code in ROUNDS else -1
        if idx < 0 or idx >= len(ROUNDS) - 1:
            return self.round_probs.get(round_code)

        current = self.round_probs.get(round_code)
        next_round = ROUNDS[idx + 1]
        next_prob = self.round_probs.get(next_round)

        if current is None or current == 0:
            return None
        if next_prob is None:
            return None
        return next_prob / current


# ── Price → probability ────────────────────────────────────────────────────────

def price_to_prob(market: dict) -> float:
    """Convert Kalshi market prices to implied probability.

    Strategy: midpoint of yes_bid / yes_ask. Fallback to last_price.
    Kalshi prices are in cents (0–100).
    """
    yes_bid = market.get("yes_bid")
    yes_ask = market.get("yes_ask")

    if yes_bid is not None and yes_ask is not None and yes_bid > 0 and yes_ask > 0:
        return (yes_bid + yes_ask) / 2 / 100

    last_price = market.get("last_price", market.get("yes_price", 0))
    if last_price and last_price > 0:
        return last_price / 100

    return 0.0


# ── Market parsing ─────────────────────────────────────────────────────────────

def _parse_team_round(market: dict) -> tuple[str | None, str | None]:
    """Extract (team_name, round_code) from a Kalshi market.

    This is the main parsing function that interprets market titles/tickers
    to figure out which team and which round they correspond to.

    ⚠️  This needs to be adapted once we see the actual market format.
    """
    title = (market.get("title") or market.get("subtitle") or "").lower()
    ticker = (market.get("ticker") or "").upper()

    # Try to identify the round from the title
    round_code = None
    for keyword, rnd in ROUND_KEYWORDS.items():
        if keyword in title:
            round_code = rnd
            break

    # Try to identify the team from the title
    team_name = None
    # Strategy: iterate through known teams and check if their name appears in the title
    for team in get_all_teams():
        if team.name.lower() in title:
            team_name = team.name
            break
        if team.kalshi_name and team.kalshi_name.lower() in title:
            team_name = team.name
            break

    return team_name, round_code


# ── Main fetch function ────────────────────────────────────────────────────────

def fetch_odds() -> list[TeamOdds]:
    """Fetch all March Madness odds from Kalshi and return structured TeamOdds.

    Returns a list of TeamOdds, one per team, with probabilities filled in
    for each round where Kalshi has a market.
    """
    if not SERIES_TICKERS:
        logger.warning("No series tickers configured — using sample odds data")
        return _generate_sample_odds()

    client = get_client()
    all_markets = []

    # Fetch markets for each configured series/event ticker
    for ticker in SERIES_TICKERS:
        logger.info("Fetching markets", series_ticker=ticker)
        try:
            markets = client.get_markets(
                series_ticker=ticker,
                limit=1000,
            )
            if isinstance(markets, dict):
                markets = markets.get("markets", [])
            all_markets.extend(markets)
            logger.info("Fetched markets", count=len(markets), series_ticker=ticker)
        except Exception:
            logger.exception("Failed to fetch markets", series_ticker=ticker)

    if not all_markets:
        logger.warning("No markets found — returning empty odds")
        return _empty_odds()

    # Build team → TeamOdds mapping
    odds_map: dict[str, TeamOdds] = {}
    for team in get_all_teams():
        odds_map[team.name] = TeamOdds(team=team)

    # Parse each market and assign probabilities
    parsed_count = 0
    for market in all_markets:
        team_name, round_code = _parse_team_round(market)
        if team_name and round_code and team_name in odds_map:
            prob = price_to_prob(market)
            odds_map[team_name].round_probs[round_code] = prob
            parsed_count += 1
            logger.debug(
                "Parsed market",
                team=team_name,
                round=round_code,
                prob=f"{prob:.1%}",
                ticker=market.get("ticker"),
            )
        else:
            logger.debug(
                "Skipped market",
                title=market.get("title", "?")[:60],
                ticker=market.get("ticker"),
                team_found=team_name,
                round_found=round_code,
            )

    logger.info("Odds parsing complete", total_markets=len(all_markets), parsed=parsed_count)
    return list(odds_map.values())


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
            "best_pick_round": to.best_pick_round,
            "best_pick_prob": to.best_pick_prob,
        })
    return snapshot
