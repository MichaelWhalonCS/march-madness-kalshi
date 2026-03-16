"""Generate a self-contained index.html from TeamOdds data."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import jinja2
import structlog

from .config import settings
from .odds import TeamOdds, best_survivor_series
from .teams import ROUND_LABELS, ROUNDS

logger = structlog.get_logger()

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _prob_display(prob: float | None) -> str:
    """Format probability for display."""
    if prob is None:
        return "—"
    if prob < 0.005:
        return "<0.1%"
    return f"{prob:.1%}"


def _prob_color(prob: float | None) -> str:
    """Return a CSS background color for the probability cell.

    Gradient: dark red (0%) → yellow (50%) → dark green (100%).
    """
    if prob is None:
        return "#1e2228"  # dark gray matching the dark theme

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
    """Format the 'Best Pick' column.

    Shows the latest round where the team has >= 70% conditional win probability.
    For teams with no safe round, shows the best available with a visual indicator.
    """
    rnd = team_odds.best_pick_round
    prob = team_odds.best_pick_prob
    if rnd is None or prob is None:
        return "—"
    return f"{rnd} ({prob:.1%})"


def _best_pick_is_safe(team_odds: TeamOdds) -> bool:
    """True if the best pick round has conditional probability >= SAFE_THRESHOLD."""
    prob = team_odds.best_pick_prob
    return prob is not None and prob >= team_odds.SAFE_THRESHOLD


def _best_pick_sort_value(team_odds: TeamOdds) -> float:
    """Numeric sort value for Best Pick: higher = more valuable.

    Encodes round index + probability so later rounds sort higher.
    """
    rnd = team_odds.best_pick_round
    prob = team_odds.best_pick_prob or 0.0
    if rnd is None:
        return -1.0
    idx = ROUNDS.index(rnd) if rnd in ROUNDS else 0
    # Round index (0-5) * 10 + probability gives a good sort
    return idx * 10 + prob


def generate_html(odds: list[TeamOdds], output_path: Path) -> None:
    """Generate the self-contained index.html and write it to output_path."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("table.html")

    # Sort by region, then seed
    sorted_odds = sorted(odds, key=lambda o: (o.team.region, o.team.seed))

    now = datetime.now(UTC)

    # Determine which rounds to show based on current round
    current_round = settings.current_round
    current_idx = ROUNDS.index(current_round) if current_round in ROUNDS else 0
    visible_rounds = ROUNDS[current_idx:]

    # "Win & Out" = P(advance past current round) - P(advance past next round)
    # i.e. wins the current game but loses the following one
    win_rnd = current_round  # the round being played now
    next_idx = current_idx + 1
    lose_rnd = ROUNDS[next_idx] if next_idx < len(ROUNDS) else None

    win_out_label = f"Win {ROUND_LABELS.get(win_rnd, win_rnd).replace('Make ', '')} & Out"

    # Build row data for the template
    rows = []
    for to in sorted_odds:
        conds = to.conditional_probs()
        round_cells = []
        for rnd in visible_rounds:
            cum_prob = to.round_probs.get(rnd)
            cond_prob = conds.get(rnd)
            round_cells.append({
                "round": rnd,
                "prob": cum_prob,
                "cond_prob": cond_prob,
                "display": _prob_display(cum_prob),
                "cond_display": _prob_display(cond_prob),
                "bg_color": _prob_color(cum_prob),
                "text_color": _prob_text_color(cum_prob),
            })

        # "Win & Out" = P(Make next round) - P(Make round after that)
        win_prob = to.round_probs.get(win_rnd)
        lose_prob = to.round_probs.get(lose_rnd) if lose_rnd else None
        if win_prob is not None and lose_prob is not None:
            win_and_out = win_prob - lose_prob
        elif win_prob is not None and lose_rnd is None:
            # Championship round — no "and out", just win prob
            win_and_out = win_prob
        else:
            win_and_out = None

        rows.append({
            "team": to.team.name,
            "seed": to.team.seed,
            "region": to.team.region,
            "eliminated": to.team.eliminated,
            "kalshi_prob": to.kalshi_prob,
            "kalshi_url": to.kalshi_url,
            "kalshi_display": _prob_display(to.kalshi_prob),
            "kalshi_bg": _prob_color(to.kalshi_prob),
            "kalshi_text": _prob_text_color(to.kalshi_prob),
            "win_and_out": win_and_out,
            "win_and_out_display": _prob_display(win_and_out),
            "win_and_out_bg": _prob_color(win_and_out),
            "win_and_out_text": _prob_text_color(win_and_out),
            "round_cells": round_cells,
            "best_pick": _best_pick_display(to),
            "best_pick_is_safe": _best_pick_is_safe(to),
            "best_pick_sort": _best_pick_sort_value(to),
        })

    # ── Suggested pick series ──────────────────────────────────────────
    suggested_series = best_survivor_series(odds, visible_rounds, top_n=3)
    # Format survival probability for display
    for i, series in enumerate(suggested_series):
        for pick in series:
            pick["cond_display"] = _prob_display(pick["cond_prob"])
            pick["cond_bg"] = _prob_color(pick["cond_prob"])
            pick["cond_text"] = _prob_text_color(pick["cond_prob"])
        survival = series[0]["survival"] if series else 0
        for pick in series:
            pick["survival_display"] = f"{survival:.1%}"
            pick["series_rank"] = i + 1

    html = template.render(
        rows=rows,
        round_labels=ROUND_LABELS,
        rounds=visible_rounds,
        current_round=current_round,
        win_out_label=win_out_label,
        updated_at=now.strftime("%Y-%m-%d %H:%M UTC"),
        team_count=len([r for r in rows if not r["eliminated"]]),
        suggested_series=suggested_series,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info("HTML generated", path=str(output_path), rows=len(rows))
