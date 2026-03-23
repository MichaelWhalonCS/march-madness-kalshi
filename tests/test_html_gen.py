"""Tests for the HTML generator."""

import tempfile
from pathlib import Path

from src.html_gen import _compute_future_value, _prob_color, _prob_display, generate_html
from src.odds import TeamOdds
from src.teams import ROUNDS, Team


def test_prob_display():
    assert _prob_display(None) == "—"
    assert _prob_display(0.0) == "<0.1%"
    assert _prob_display(0.003) == "<0.1%"
    assert _prob_display(0.97) == "97.0%"
    assert _prob_display(0.5) == "50.0%"
    assert _prob_display(1.0) == "100.0%"
    assert _prob_display(0.856) == "85.6%"


def test_prob_color_returns_rgb():
    color = _prob_color(0.5)
    assert color.startswith("rgb(")
    color_none = _prob_color(None)
    assert color_none == "#1e2228"


def test_generate_html_creates_file():
    team = Team(name="TestTeam", seed=1, region="East")
    odds = [
        TeamOdds(
            team=team,
            round_probs={"R64": 0.95, "R32": 0.80},
            kalshi_prob=0.93,
            kalshi_url="https://kalshi.com/markets/kxncaambgame/kxncaambgame-26mar19test",
            game_day="Thu",
        ),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "index.html"
        generate_html(odds, output)
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "TestTeam" in content
        # In R64, the displayed R64 probability now uses Kalshi per-game odds
        # (0.93) rather than futures "qualify for R32" (0.95).
        assert "93.0%" in content
        assert "93.0%" in content  # Kalshi odds column
        assert "Kalshi" in content
        assert "March Madness" in content
        # Kalshi cell should link to the specific market
        assert "kalshi.com/markets/kxncaambgame/kxncaambgame-26mar19test" in content
        # Day column should show for R64
        assert "Thu" in content
        # FV table should appear for teams with data
        assert "Future Value" in content
        # Info section should have methodology explanations
        assert "Tournament Futures" in content
        assert "Per-Game Markets" in content
        assert "conditional" in content.lower()


def test_generate_html_empty_odds():
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "index.html"
        generate_html([], output)
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "No odds data yet" in content


def test_compute_future_value_r64():
    """FV for R64: cond_R64 - (cum_R32 + 2*cum_S16 + 4*cum_E8 + 8*cum_F4 + 16*cum_Champ)."""
    team = Team(name="Duke", seed=1, region="East")
    to = TeamOdds(
        team=team,
        round_probs={
            "R64": 0.97, "R32": 0.85, "S16": 0.65,
            "E8": 0.40, "F4": 0.20, "Championship": 0.10,
        },
    )
    visible = ROUNDS  # all rounds from R64
    fv = _compute_future_value(to, "R64", visible)

    assert fv["win_current"] == 0.97  # conditional R64 = cumulative R64
    expected_fw = 0.85 + 2 * 0.65 + 4 * 0.40 + 8 * 0.20 + 16 * 0.10
    assert abs(fv["future_weighted"] - expected_fw) < 1e-9
    assert abs(fv["fv"] - (0.97 - expected_fw)) < 1e-9
    assert len(fv["future_terms"]) == 5  # R32, S16, E8, F4, Championship


def test_compute_future_value_later_round():
    """FV adapts when current round is R32 — fewer future terms."""
    team = Team(name="Duke", seed=1, region="East")
    to = TeamOdds(
        team=team,
        round_probs={
            "R64": 0.97, "R32": 0.85, "S16": 0.65,
            "E8": 0.40, "F4": 0.20, "Championship": 0.10,
        },
    )
    visible = ROUNDS[1:]  # R32 onward
    fv = _compute_future_value(to, "R32", visible)

    # cond R32 = cum_R32 / cum_R64 = 0.85 / 0.97
    cond_r32 = 0.85 / 0.97
    assert abs(fv["win_current"] - cond_r32) < 0.001
    # Future: S16, E8, F4, Championship with weights 1, 2, 4, 8
    expected_fw = 0.65 + 2 * 0.40 + 4 * 0.20 + 8 * 0.10
    assert abs(fv["future_weighted"] - expected_fw) < 1e-9
    assert len(fv["future_terms"]) == 4


def test_generate_html_fv_uses_kalshi_fallback_when_prev_round_missing():
    """FV should still render in S16 when R32 cumulative market is unavailable."""
    team = Team(name="FallbackTeam", seed=3, region="South")
    odds = [
        TeamOdds(
            team=team,
            round_probs={"S16": 0.55, "E8": 0.30, "F4": 0.16, "Championship": 0.06},
            kalshi_prob=0.60,
            kalshi_url="https://kalshi.com/markets/kxncaambgame/kxncaambgame-26mar27fallback",
            game_day="Fri",
            game_date="Mar 27",
        ),
    ]

    from src.html_gen import settings

    original_round = settings.current_round
    settings.current_round = "S16"
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "index.html"
            generate_html(odds, output)
            content = output.read_text(encoding="utf-8")
            assert "Future Value" in content
            assert "FallbackTeam" in content
            assert "60.0%" in content
    finally:
        settings.current_round = original_round
