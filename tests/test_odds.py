"""Tests for the odds module."""

from src.odds import price_to_prob, TeamOdds
from src.teams import Team


def test_price_to_prob_midpoint():
    """Midpoint of bid/ask."""
    market = {"yes_bid": 60, "yes_ask": 70}
    assert price_to_prob(market) == 0.65


def test_price_to_prob_last_price_fallback():
    """Falls back to last_price when no bid/ask."""
    market = {"yes_bid": 0, "yes_ask": 0, "last_price": 45}
    assert price_to_prob(market) == 0.45


def test_price_to_prob_zero():
    """Returns 0 when no price data."""
    assert price_to_prob({}) == 0.0


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
