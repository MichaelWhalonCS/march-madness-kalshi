"""Tests for the odds module."""

from src.odds import TeamOdds, _parse_ticker, price_to_prob
from src.teams import Team


def test_price_to_prob_prefers_last_price():
    """last_price_dollars is the primary source (matches Kalshi display)."""
    market = {"yes_bid_dollars": 0.60, "yes_ask_dollars": 0.70, "last_price_dollars": 0.65}
    assert price_to_prob(market) == 0.65


def test_price_to_prob_last_price_over_midpoint():
    """last_price is preferred even when bid/ask midpoint differs."""
    # Duke-style: bid=0.99, ask=1.00, last=0.99 → should return 0.99 not 0.995
    market = {"yes_bid_dollars": 0.99, "yes_ask_dollars": 1.00, "last_price_dollars": 0.99}
    assert price_to_prob(market) == 0.99


def test_price_to_prob_bid_fallback():
    """Falls back to yes_bid when no last_price."""
    market = {"yes_bid_dollars": 0.60, "yes_ask_dollars": 0.70}
    assert price_to_prob(market) == 0.60


def test_price_to_prob_cents_normalized():
    """Cents-based values (>1) auto-divided by 100."""
    market = {"last_price": 65}
    assert price_to_prob(market) == 0.65


def test_price_to_prob_last_price_only():
    """Works with only last_price, no bid/ask."""
    market = {"yes_bid_dollars": 0.0, "yes_ask_dollars": 0.0, "last_price_dollars": 0.45}
    assert price_to_prob(market) == 0.45


def test_price_to_prob_zero():
    """Returns 0 when no price data."""
    assert price_to_prob({}) == 0.0


def test_team_odds_kalshi_prob():
    """TeamOdds carries kalshi_prob, kalshi_url, and game_day fields."""
    team = Team(name="Duke", seed=1, region="East")
    odds = TeamOdds(
        team=team,
        round_probs={"R64": 0.97},
        kalshi_prob=0.95,
        kalshi_url="https://kalshi.com/markets/kxncaambgame/kxncaambgame-26mar19sieduke",
        game_day="Thu",
    )
    assert odds.kalshi_prob == 0.95
    assert odds.kalshi_url == "https://kalshi.com/markets/kxncaambgame/kxncaambgame-26mar19sieduke"
    assert odds.game_day == "Thu"


def test_team_odds_best_pick():
    team = Team(name="Duke", seed=1, region="East")
    odds = TeamOdds(
        team=team,
        round_probs={"R64": 0.97, "R32": 0.82, "S16": 0.55, "E8": 0.35},
    )
    # Conditional probs: R64=0.97, R32=0.82/0.97≈0.845, S16=0.55/0.82≈0.671, E8=0.35/0.55≈0.636
    # Latest round with conditional >=70% is R32
    assert odds.best_pick_round == "R32"
    assert odds.best_pick_prob is not None
    assert abs(odds.best_pick_prob - 0.82 / 0.97) < 0.001


def test_team_odds_conditional_prob():
    team = Team(name="Duke", seed=1, region="East")
    odds = TeamOdds(
        team=team,
        round_probs={"R64": 0.97, "R32": 0.82, "S16": 0.55},
    )
    # P(win R32 game | made R32) = P(make S16) / P(make R32) = 0.82 / 0.97
    cond_r32 = odds.conditional_prob("R32")
    assert cond_r32 is not None
    assert abs(cond_r32 - 0.82 / 0.97) < 0.001

    # P(win S16 game | made S16) = P(make E8) / P(make S16) — but no E8 data
    # so test S16 conditional differently:
    # Actually in conditional_probs, S16 = round_probs["S16"] / round_probs["R32"]
    cond_s16 = odds.conditional_prob("S16")
    assert cond_s16 is not None
    assert abs(cond_s16 - 0.55 / 0.82) < 0.001


def test_team_odds_empty():
    team = Team(name="TBD", seed=16, region="East")
    odds = TeamOdds(team=team)
    assert odds.best_pick_round is None
    assert odds.best_pick_prob is None
    assert odds.game_day is None


def test_parse_ticker_extracts_day():
    """_parse_ticker returns (abbr, round_code, day_of_week)."""
    abbr, rnd, day = _parse_ticker("KXNCAAMBGAME-26MAR19SIEDUKE-DUKE")
    assert abbr == "DUKE"
    assert rnd == "R64"
    assert day == "Thu"

    abbr2, rnd2, day2 = _parse_ticker("KXNCAAMBGAME-26MAR21DUKEALA-ALA")
    assert abbr2 == "ALA"
    assert rnd2 == "R32"
    assert day2 == "Sat"

    # Invalid ticker
    a, r, d = _parse_ticker("BADTICKER")
    assert a is None and r is None and d is None
