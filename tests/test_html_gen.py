"""Tests for the HTML generator."""

import tempfile
from pathlib import Path

from src.html_gen import _prob_color, _prob_display, generate_html
from src.odds import TeamOdds
from src.teams import Team


def test_prob_display():
    assert _prob_display(None) == "—"
    assert _prob_display(0.0) == "<1%"
    assert _prob_display(0.003) == "<1%"
    assert _prob_display(0.97) == "97%"
    assert _prob_display(0.5) == "50%"
    assert _prob_display(1.0) == "100%"


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
        ),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "index.html"
        generate_html(odds, output)
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "TestTeam" in content
        assert "95%" in content
        assert "93%" in content  # Kalshi odds column
        assert "Kalshi" in content
        assert "March Madness" in content
        # Kalshi cell should link to the specific market
        assert "kalshi.com/markets/kxncaambgame/kxncaambgame-26mar19test" in content
        # Info section should have methodology explanations
        assert "ESPN BPI" in content
        assert "Basketball Power Index" in content
        assert "conditional" in content.lower()


def test_generate_html_empty_odds():
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "index.html"
        generate_html([], output)
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "No odds data yet" in content
