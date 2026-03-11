"""Generate a self-contained index.html from TeamOdds data."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import jinja2
import structlog

from .odds import TeamOdds
from .teams import ROUNDS, ROUND_LABELS

logger = structlog.get_logger()

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _prob_display(prob: float | None) -> str:
    """Format probability for display."""
    if prob is None:
        return "—"
    if prob < 0.005:
        return "<1%"
    return f"{prob:.0%}"


def _prob_color(prob: float | None) -> str:
    """Return a CSS background color for the probability cell.

    Gradient: dark red (0%) → yellow (50%) → dark green (100%).
    """
    if prob is None:
        return "#f8f9fa"  # light gray for missing

    # Clamp
    p = max(0.0, min(1.0, prob))

    if p < 0.5:
        # Red → Yellow
        ratio = p / 0.5
        r = int(220 - ratio * 40)
        g = int(60 + ratio * 160)
        b = int(60 - ratio * 10)
    else:
        # Yellow → Green
        ratio = (p - 0.5) / 0.5
        r = int(180 - ratio * 140)
        g = int(220 - ratio * 40)
        b = int(50 + ratio * 30)

    return f"rgb({r},{g},{b})"


def _prob_text_color(prob: float | None) -> str:
    """Return text color — white for very low/very high probs, dark otherwise."""
    if prob is None:
        return "#6c757d"
    if prob < 0.15 or prob > 0.90:
        return "#ffffff"
    return "#1a1a1a"


def _best_pick_display(team_odds: TeamOdds) -> str:
    """Format the 'Best Pick' column."""
    rnd = team_odds.best_pick_round
    prob = team_odds.best_pick_prob
    if rnd is None or prob is None:
        return "—"
    return f"{rnd} ({prob:.0%})"


def generate_html(odds: list[TeamOdds], output_path: Path) -> None:
    """Generate the self-contained index.html and write it to output_path."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("table.html")

    # Sort by region, then seed
    sorted_odds = sorted(odds, key=lambda o: (o.team.region, o.team.seed))

    now = datetime.now(timezone.utc)

    # Build row data for the template
    rows = []
    for to in sorted_odds:
        round_cells = []
        for rnd in ROUNDS:
            prob = to.round_probs.get(rnd)
            round_cells.append({
                "round": rnd,
                "prob": prob,
                "display": _prob_display(prob),
                "bg_color": _prob_color(prob),
                "text_color": _prob_text_color(prob),
            })

        rows.append({
            "team": to.team.name,
            "seed": to.team.seed,
            "region": to.team.region,
            "eliminated": to.team.eliminated,
            "round_cells": round_cells,
            "best_pick": _best_pick_display(to),
        })

    html = template.render(
        rows=rows,
        round_labels=ROUND_LABELS,
        rounds=ROUNDS,
        updated_at=now.strftime("%Y-%m-%d %H:%M UTC"),
        team_count=len([r for r in rows if not r["eliminated"]]),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info("HTML generated", path=str(output_path), rows=len(rows))
