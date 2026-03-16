"""Tests for the Kalshi tournament futures integration."""

from src.odds import (
    _FUTURES_EVENT_TO_ROUND,
    CHAMP_EVENT,
    FUTURES_SERIES,
    price_to_prob,
)


def test_futures_event_to_round_covers_all():
    """All five advancement rounds are mapped."""
    rounds = set(_FUTURES_EVENT_TO_ROUND.values())
    assert rounds == {"R64", "R32", "S16", "E8", "F4"}


def test_futures_series_constants():
    """Series and event constants are correct."""
    assert FUTURES_SERIES == "KXMARMADROUND"
    assert CHAMP_EVENT == "KXMARMAD-26"


def test_price_to_prob_futures_format():
    """Futures markets use dollar-denomination just like per-game markets."""
    market = {"yes_bid_dollars": "0.5900", "yes_ask_dollars": "0.6100"}
    prob = price_to_prob(market)
    assert abs(prob - 0.60) < 0.01


def test_price_to_prob_low_prob_futures():
    """Championship long-shots have very low prices."""
    market = {"yes_bid_dollars": "0.0000", "yes_ask_dollars": "0.0100", "last_price_dollars": "0.0100"}
    prob = price_to_prob(market)
    assert prob == 0.01  # last_price fallback
