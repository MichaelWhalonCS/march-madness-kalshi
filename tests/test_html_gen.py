"""Tests for the HTML generator."""

from pathlib import Path
import tempfile

from src.html_gen import generate_html, _prob_display, _prob_color
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
        TeamOdds(team=team, round_probs={"R64": 0.95, "R32": 0.80}),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "index.html"
        generate_html(odds, output)
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "TestTeam" in content
        assert "95%" in content
        assert "March Madness" in content


def test_generate_html_empty_odds():
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "index.html"
        generate_html([], output)
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "No odds data yet" in content
