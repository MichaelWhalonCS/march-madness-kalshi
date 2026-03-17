"""Fetch March Madness odds from Kalshi and structure them for the table.

All data comes from Kalshi prediction markets:

1. **Per-game markets** (``KXNCAAMBGAME`` series)
   Each game has two binary markets (one per team).  Prices are in dollars
   (0.00–1.00).  We use the last traded price as the implied win
   probability, falling back to the best bid when no trade has occurred.

2. **Tournament futures** (``KXMARMADROUND`` + ``KXMARMAD`` series)
   Per-team, per-round advancement markets — e.g. "Will Duke qualify for
   the men's Sweet Sixteen?"  These provide cumulative advancement
   probabilities for every round (R32 through Championship).

   Kalshi round event → our round_probs key:
     KXMARMADROUND-26RO32  → R64   (reaching R32 = surviving R64)
     KXMARMADROUND-26S16   → R32   (reaching S16 = surviving R32)
     KXMARMADROUND-26E8    → S16
     KXMARMADROUND-26F4    → E8
     KXMARMADROUND-26T2    → F4
     KXMARMAD-26           → Championship   (winning it all)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import structlog

from .kalshi_client import get_client
from .teams import KALSHI_ABBR_MAP, ROUNDS, Team, get_all_teams

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

# Dates → day-of-week abbreviation (March Madness 2026 calendar).
_DATE_TO_DAY: dict[str, str] = {
    "MAR17": "Tue",
    "MAR18": "Wed",
    "MAR19": "Thu",
    "MAR20": "Fri",
    "MAR21": "Sat",
    "MAR22": "Sun",
    "MAR26": "Thu",
    "MAR27": "Fri",
    "MAR28": "Sat",
    "MAR29": "Sun",
    "APR04": "Sat",
    "APR06": "Mon",
}

# ── Futures configuration ──────────────────────────────────────────────────────

FUTURES_SERIES = "KXMARMADROUND"       # per-round advancement futures
CHAMP_EVENT   = "KXMARMAD-26"          # championship winner event

# Kalshi futures event suffix → our cumulative round_probs key.
# "Reach Round of 32" = survived R64, so maps to round_probs["R64"].
_FUTURES_EVENT_TO_ROUND: dict[str, str] = {
    "26RO32": "R64",
    "26S16":  "R32",
    "26E8":   "S16",
    "26F4":   "E8",
    "26T2":   "F4",
}

_KALSHI_FUTURES_URL_BASE = "https://kalshi.com/markets/kxmarmadround"


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class TeamOdds:
    """Odds for a single team across all rounds."""

    team: Team
    round_probs: dict[str, float | None] = field(default_factory=dict)
    # round_probs maps round code → implied probability (0.0–1.0), None if no market
    round_urls: dict[str, str] = field(default_factory=dict)
    # round_urls maps round code → Kalshi market page URL for that round

    # Kalshi per-game market probability for the current round (None if no market)
    kalshi_prob: float | None = None
    # Direct link to this team's Kalshi market page (None if no market)
    kalshi_url: str | None = None
    # Day of week for the team's current-round game (e.g. "Thu", "Fri")
    game_day: str | None = None

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

def _normalize_price(val) -> float | None:
    """Convert a price value (dollars or cents) to a 0.0–1.0 probability."""
    if val is None:
        return None
    v = float(val)
    if v <= 0:
        return None
    # Cents (>1) → dollars
    return v / 100 if v > 1 else v


def price_to_prob(market: dict) -> float:
    """Convert Kalshi market prices to implied probability.

    Strategy: prefer **last_price** (most recent trade, matches what Kalshi
    displays on their website).  Fall back to **yes_bid** (current best bid),
    then to the bid/ask midpoint as a last resort.

    The previous midpoint-first approach systematically inflated favourites
    because at price extremes (e.g. yes_bid=0.99, yes_ask=1.00) the ask
    hits the $1 ceiling, pulling the midpoint above the true market price.

    Kalshi prices are in dollars (0.00–1.00).  Cent-denominated values (>1)
    are auto-normalised.
    """
    # ── Dollar-denominated fields (pykalshi 0.4.0+) ─────────────────────
    last_price_raw = market.get("last_price_dollars") or market.get("last_price")
    yes_bid_raw = market.get("yes_bid_dollars") or market.get("yes_bid")
    yes_ask_raw = market.get("yes_ask_dollars") or market.get("yes_ask")

    last = _normalize_price(last_price_raw)
    bid = _normalize_price(yes_bid_raw)
    ask = _normalize_price(yes_ask_raw)

    # 1. Last traded price — actual market activity, closest to display price
    if last is not None:
        return last

    # 2. Best bid — what someone will actually pay right now
    if bid is not None:
        return bid

    # 3. Midpoint — only when no last price or bid available
    if bid is not None and ask is not None:
        return (bid + ask) / 2

    # 4. Ask alone (very illiquid market)
    if ask is not None:
        return ask

    return 0.0


# ── Market parsing ─────────────────────────────────────────────────────────────

def _parse_ticker(ticker: str) -> tuple[str | None, str | None, str | None]:
    """Extract (kalshi_abbr, round_code, day_of_week) from a Kalshi market ticker.

    Ticker format: KXNCAAMBGAME-26MAR19SIEDUKE-DUKE
                   ^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^  ^^^^
                   series        date+matchup      team abbr

    Returns (team_kalshi_abbr, round_code, day_of_week) or (None, None, None).
    """
    parts = ticker.split("-")
    if len(parts) < 3 or parts[0] != SERIES_TICKER:
        return None, None, None

    team_abbr = parts[-1]  # Last segment is the team abbreviation
    game_part = parts[1]   # e.g. "26MAR19SIEDUKE"

    # Extract date: first 7 chars = "26MAR19" → take chars 2..7 = "MAR19"
    if len(game_part) < 7:
        return None, None, None
    date_str = game_part[2:7]  # e.g. "MAR19"

    round_code = _DATE_TO_ROUND.get(date_str)
    day_of_week = _DATE_TO_DAY.get(date_str)
    return team_abbr, round_code, day_of_week


# ── Main fetch function ────────────────────────────────────────────────────────

# Kalshi market page URL pattern:
# https://kalshi.com/markets/kxncaambgame/{event_ticker_lowercase}
_KALSHI_MARKET_URL_BASE = "https://kalshi.com/markets/kxncaambgame"


def _market_to_dict(market) -> dict:
    """Normalise a pykalshi market to a plain dict."""
    if isinstance(market, dict):
        return market
    if hasattr(market, "data") and hasattr(market.data, "model_dump"):
        return market.data.model_dump()
    return market.__dict__


# Settled / finalized statuses to skip — these are games already played
_CLOSED_STATUSES = {"finalized", "settled", "closed", "determined"}


def _is_closed(mdict: dict) -> bool:
    """Return True if the market status indicates it's already resolved."""
    status = mdict.get("status", "")
    status_str = status.value if hasattr(status, "value") else str(status)
    return status_str.lower() in _CLOSED_STATUSES


def _fetch_kalshi_probs() -> tuple[dict[str, float], dict[str, str], dict[str, str]]:
    """Fetch current-round Kalshi market probabilities, keyed by team name.

    Returns:
        (probs, urls, days) where:
            probs: dict team_name → implied probability (0.0–1.0)
            urls:  dict team_name → Kalshi market page URL
            days:  dict team_name → day-of-week abbreviation ("Thu", "Fri", etc.)
        All empty if Kalshi API is unreachable or has no markets.
    """
    try:
        client = get_client()
        markets = client.get_markets(series_ticker=SERIES_TICKER, limit=1000)
        if isinstance(markets, dict):
            markets = markets.get("markets", [])
        if hasattr(markets, "to_dicts"):
            markets = markets.to_dicts()
    except Exception:
        logger.warning("Could not fetch Kalshi per-game markets")
        return {}, {}, {}

    probs: dict[str, float] = {}
    urls: dict[str, str] = {}
    days: dict[str, str] = {}
    skipped = 0
    for market in markets:
        mdict = _market_to_dict(market)

        if _is_closed(mdict):
            skipped += 1
            continue

        ticker = mdict.get("ticker", "")
        event_ticker = mdict.get("event_ticker", "")
        team_abbr, round_code, day_of_week = _parse_ticker(ticker)
        if not team_abbr:
            continue

        team_obj = KALSHI_ABBR_MAP.get(team_abbr)
        if not team_obj:
            continue

        prob = price_to_prob(mdict)
        if prob > 0:
            probs[team_obj.name] = prob
            if event_ticker:
                urls[team_obj.name] = f"{_KALSHI_MARKET_URL_BASE}/{event_ticker.lower()}"
            if day_of_week:
                days[team_obj.name] = day_of_week
            logger.debug("Kalshi market", team=team_obj.name, prob=f"{prob:.1%}", ticker=ticker)

    logger.info("Kalshi per-game markets fetched", parsed=len(probs), skipped_closed=skipped)
    return probs, urls, days


# ── Kalshi tournament futures ──────────────────────────────────────────────────

def _fetch_all_markets(client, **kwargs) -> list[dict]:
    """Fetch markets via pykalshi and convert to plain dicts.

    pykalshi handles cursor-based pagination internally when limit > 200,
    so a single call suffices.
    """
    result = client.get_markets(**kwargs, limit=1000)
    # result may be a DataFrameList[Market], a dict, or a plain list
    if isinstance(result, dict):
        raw = result.get("markets", [])
    elif hasattr(result, "to_dicts"):
        raw = result.to_dicts()
    else:
        raw = list(result)
    return [_market_to_dict(m) for m in raw]


def _fetch_kalshi_futures() -> tuple[dict[str, dict[str, float]], dict[str, dict[str, str]]]:
    """Fetch Kalshi tournament futures and return cumulative round probabilities.

    Combines the KXMARMADROUND series (R64 → F4) with the KXMARMAD-26
    championship event to build:
        probs: team_name → {round_code → probability (0.0–1.0)}
        urls:  team_name → {round_code → Kalshi market URL}

    This replaces ESPN BPI as the source for multi-round advancement data.
    """
    try:
        client = get_client()
    except Exception:
        logger.warning("Could not initialise Kalshi client for futures")
        return {}, {}

    # ── 1. Fetch KXMARMADROUND advancement markets ─────────────────────────
    try:
        round_markets = _fetch_all_markets(client, series_ticker=FUTURES_SERIES)
    except Exception:
        logger.exception("Failed to fetch KXMARMADROUND markets")
        round_markets = []

    result: dict[str, dict[str, float]] = {}
    urls: dict[str, dict[str, str]] = {}

    for mdict in round_markets:
        if _is_closed(mdict):
            continue

        ticker = mdict.get("ticker", "")
        event_ticker = mdict.get("event_ticker", "")
        # KXMARMADROUND-26RO32-UGA → parts = ["KXMARMADROUND", "26RO32", "UGA"]
        parts = ticker.split("-")
        if len(parts) < 3:
            continue

        team_abbr = parts[-1]
        event_suffix = parts[1]  # e.g. "26RO32"

        round_code = _FUTURES_EVENT_TO_ROUND.get(event_suffix)
        if round_code is None:
            continue

        team_obj = KALSHI_ABBR_MAP.get(team_abbr)
        if team_obj is None:
            continue

        prob = price_to_prob(mdict)
        if prob > 0:
            result.setdefault(team_obj.name, {})[round_code] = prob
            if event_ticker:
                urls.setdefault(team_obj.name, {})[round_code] = (
                    f"{_KALSHI_FUTURES_URL_BASE}/{event_ticker.lower()}"
                )

    # ── 2. Fetch KXMARMAD-26 championship markets ──────────────────────────
    try:
        champ_markets = _fetch_all_markets(client, event_ticker=CHAMP_EVENT)
    except Exception:
        logger.exception("Failed to fetch KXMARMAD championship markets")
        champ_markets = []

    for mdict in champ_markets:
        if _is_closed(mdict):
            continue

        ticker = mdict.get("ticker", "")
        # KXMARMAD-26-UGA → parts = ["KXMARMAD", "26", "UGA"]
        parts = ticker.split("-")
        if len(parts) < 3:
            continue

        team_abbr = parts[-1]
        team_obj = KALSHI_ABBR_MAP.get(team_abbr)
        if team_obj is None:
            continue

        prob = price_to_prob(mdict)
        if prob > 0:
            result.setdefault(team_obj.name, {})["Championship"] = prob
            event_ticker = mdict.get("event_ticker", "")
            if event_ticker:
                urls.setdefault(team_obj.name, {})["Championship"] = (
                    f"https://kalshi.com/markets/kxmarmad/{event_ticker.lower()}"
                )

    logger.info(
        "Kalshi futures fetched",
        teams_with_futures=len(result),
        rounds_found=sorted({r for probs in result.values() for r in probs}),
    )
    return result, urls


def fetch_odds() -> list[TeamOdds]:
    """Fetch odds entirely from Kalshi prediction markets.

    Kalshi tournament futures provide cumulative advancement probabilities
    for all rounds (replacing ESPN BPI).  Per-game markets provide the
    current-round win probability shown in the dedicated Kalshi column.
    """

    # 1. Kalshi futures — multi-round cumulative advancement probabilities
    futures_data, futures_urls = _fetch_kalshi_futures()

    if not futures_data:
        logger.warning("No Kalshi futures data — falling back to sample odds")
        return _generate_sample_odds()

    # 2. Kalshi per-game — current round market prices
    kalshi_probs, kalshi_urls, kalshi_days = _fetch_kalshi_probs()

    # 3. Build TeamOdds for every team
    result: list[TeamOdds] = []
    for team in get_all_teams():
        round_probs = futures_data.get(team.name, {})
        round_urls = futures_urls.get(team.name, {})
        kalshi_prob = kalshi_probs.get(team.name)
        kalshi_url = kalshi_urls.get(team.name)
        game_day = kalshi_days.get(team.name)

        result.append(TeamOdds(
            team=team,
            round_probs=round_probs,
            round_urls=round_urls,
            kalshi_prob=kalshi_prob,
            kalshi_url=kalshi_url,
            game_day=game_day,
        ))

    teams_with_futures = sum(1 for to in result if to.round_probs)
    teams_with_kalshi = sum(1 for to in result if to.kalshi_prob is not None)
    logger.info(
        "Odds assembled",
        total_teams=len(result),
        with_futures=teams_with_futures,
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


def best_survivor_series(
    odds: list[TeamOdds],
    visible_rounds: list[str],
    top_n: int = 3,
) -> list[list[dict]]:
    """Find the top-N pick series for a survivor pool.

    A valid series assigns exactly one team to each visible round, with no
    team used more than once.  The "score" is the product of conditional
    game-win probabilities — i.e. the probability of surviving all rounds.

    Uses a greedy beam-search (width=200) to keep it fast (~68 teams × 6 rounds).

    Returns a list of series, each series being a list of dicts:
        [{"round": "R64", "team": "Duke", "seed": 1, "region": "South",
          "cond_prob": 0.97}, ...]
    sorted by descending overall survival probability.
    """
    import heapq

    if not visible_rounds or not odds:
        return []

    # Pre-compute conditional probs for every team
    team_conds: list[tuple[TeamOdds, dict[str, float | None]]] = [
        (to, to.conditional_probs()) for to in odds if not to.team.eliminated
    ]

    # Beam search: each state is (neg_log_score, picks_so_far, used_team_names)
    # We use negative log-prob so heapq gives us highest-prob first.
    import math

    BEAM_WIDTH = 200
    # Initial beam: empty picks
    beam: list[tuple[float, list[dict], frozenset[str]]] = [(0.0, [], frozenset())]

    for rnd in visible_rounds:
        next_beam: list[tuple[float, list[dict], frozenset[str]]] = []
        for neg_log, picks, used in beam:
            for to, conds in team_conds:
                if to.team.name in used:
                    continue
                cp = conds.get(rnd)
                if cp is None or cp <= 0:
                    continue
                new_neg_log = neg_log - math.log(cp)
                new_picks = picks + [{
                    "round": rnd,
                    "team": to.team.name,
                    "seed": to.team.seed,
                    "region": to.team.region,
                    "cond_prob": cp,
                }]
                new_used = used | {to.team.name}
                next_beam.append((new_neg_log, new_picks, new_used))
        # Keep only the best BEAM_WIDTH candidates
        if next_beam:
            next_beam.sort(key=lambda x: x[0])
            beam = next_beam[:BEAM_WIDTH]
        else:
            break  # no viable expansions

    # Extract top-N unique series (by team set) and compute survival prob
    seen: set[frozenset[str]] = set()
    results: list[tuple[float, list[dict]]] = []
    for neg_log, picks, used in beam:
        if used in seen:
            continue
        seen.add(used)
        survival = math.exp(-neg_log)
        # Deep-copy picks so shared dicts across beam entries don't collide
        picks_copy = [dict(p) for p in picks]
        for pick in picks_copy:
            pick["survival"] = survival
        results.append((survival, picks_copy))
        if len(results) >= top_n:
            break

    # Sort descending by survival probability
    results.sort(key=lambda x: -x[0])
    return [series for _, series in results]


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
            "round_urls": dict(to.round_urls),
            "kalshi_prob": to.kalshi_prob,
            "kalshi_url": to.kalshi_url,
            "game_day": to.game_day,
            "best_pick_round": to.best_pick_round,
            "best_pick_prob": to.best_pick_prob,
        })
    return snapshot
