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


# ── Future Value weights ───────────────────────────────────────────────────────
# Each subsequent future round is weighted 2× more than the previous one,
# reflecting increasing survivor-pool value of advancing deeper.
_FV_BASE = 2  # multiplier base — future_round_i gets weight _FV_BASE^i


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


def _compute_future_value(
    to: TeamOdds,
    current_round: str,
    visible_rounds: list[str],
) -> dict:
    """Compute the Weighted Future Value for a team.

    FV = %win_next_rd − (1×cum_future1 + 2×cum_future2 + 4×cum_future3 + …)

    A **high** (positive) FV means the team is useful now but doesn't contribute
    much to future rounds → use them this round.
    A **low** (negative) FV means the team has significant remaining value →
    consider saving them for a later round.

    Returns a dict with:
      win_current: conditional win probability for the current round
      future_weighted: the weighted sum of future cumulative probabilities
      fv: the Future Value score
      future_terms: list of (round_label, weight, cumulative_prob) tuples
    """
    conds = to.conditional_probs()
    win_current = conds.get(current_round)

    # Future rounds = all visible rounds after the current one
    current_idx_in_visible = visible_rounds.index(current_round) if current_round in visible_rounds else 0
    future_rounds = visible_rounds[current_idx_in_visible + 1:]

    future_weighted = 0.0
    future_terms = []
    for i, rnd in enumerate(future_rounds):
        weight = _FV_BASE ** i  # 1, 2, 4, 8, 16 …
        cum_prob = to.round_probs.get(rnd)
        prob_val = cum_prob if cum_prob is not None else 0.0
        future_weighted += weight * prob_val
        future_terms.append({
            "round": rnd,
            "label": ROUND_LABELS.get(rnd, rnd),
            "weight": weight,
            "prob": cum_prob,
        })

    if win_current is not None:
        fv = win_current - future_weighted
    else:
        fv = None

    return {
        "win_current": win_current,
        "future_weighted": future_weighted,
        "fv": fv,
        "future_terms": future_terms,
    }


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
                "url": to.round_urls.get(rnd),
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
            "game_day": to.game_day or "",
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

    # ── Suggested pick series (disabled — conditional probs from thin
    #    futures markets are too unreliable for beam search to produce
    #    trustworthy results; pass empty list to hide the section) ───────
    # suggested_series = best_survivor_series(odds, visible_rounds, top_n=3)
    suggested_series: list[list[dict]] = []

    # ── Future Value table ─────────────────────────────────────────────
    fv_rows = []
    for to in sorted_odds:
        if to.team.eliminated:
            continue
        fv_data = _compute_future_value(to, current_round, visible_rounds)
        if fv_data["fv"] is None:
            continue
        fv_rows.append({
            "team": to.team.name,
            "seed": to.team.seed,
            "region": to.team.region,
            "kalshi_url": to.kalshi_url,
            "win_current": fv_data["win_current"],
            "win_current_display": _prob_display(fv_data["win_current"]),
            "win_current_bg": _prob_color(fv_data["win_current"]),
            "win_current_text": _prob_text_color(fv_data["win_current"]),
            "future_weighted": fv_data["future_weighted"],
            "future_weighted_display": f"{fv_data['future_weighted']:.2f}",
            "fv": fv_data["fv"],
            "fv_display": f"{fv_data['fv']:+.2f}",
            "future_terms": [
                {
                    "label": t["label"],
                    "weight": t["weight"],
                    "prob": t["prob"],
                    "display": _prob_display(t["prob"]),
                    "weighted": f"{t['weight'] * (t['prob'] or 0):.2f}",
                    "weighted_val": t["weight"] * (t["prob"] or 0),
                    "url": to.round_urls.get(t["round"]),
                }
                for t in fv_data["future_terms"]
            ],
        })
    # Sort by FV descending — highest FV = "use now" at top
    fv_rows.sort(key=lambda r: r["fv"], reverse=True)

    # Collect unique game days for the day-of-week filter (R64/R32 only)
    show_day_filter = current_round in ("R64", "R32")
    # Ordered list of unique days preserving natural weekday order
    _DAY_ORDER = ["Tue", "Wed", "Thu", "Fri", "Sat", "Sun", "Mon"]
    game_days_set = {r["game_day"] for r in rows if r["game_day"]}
    game_days = [d for d in _DAY_ORDER if d in game_days_set]
    # Format survival probability for display
    # Build a lookup: team_name → round_urls dict for suggested-series links
    _team_urls = {to.team.name: to.round_urls for to in odds}

    for i, series in enumerate(suggested_series):
        for pick in series:
            pick["cond_display"] = _prob_display(pick["cond_prob"])
            pick["cond_bg"] = _prob_color(pick["cond_prob"])
            pick["cond_text"] = _prob_text_color(pick["cond_prob"])
            # Ensure round_url is present (beam search already sets it)
            if "round_url" not in pick:
                pick["round_url"] = _team_urls.get(pick["team"], {}).get(pick["round"])
        survival = series[0]["survival"] if series else 0
        for pick in series:
            pick["survival_display"] = f"{survival:.1%}"
            pick["series_rank"] = i + 1

    # FV table column headers (future rounds with weights)
    fv_future_headers = []
    current_idx_rounds = visible_rounds.index(current_round) if current_round in visible_rounds else 0
    for i, rnd in enumerate(visible_rounds[current_idx_rounds + 1:]):
        weight = _FV_BASE ** i
        fv_future_headers.append({
            "label": ROUND_LABELS.get(rnd, rnd),
            "weight": weight,
        })

    html = template.render(
        rows=rows,
        round_labels=ROUND_LABELS,
        rounds=visible_rounds,
        current_round=current_round,
        win_out_label=win_out_label,
        updated_at=now.strftime("%Y-%m-%d %H:%M UTC"),
        team_count=len([r for r in rows if not r["eliminated"]]),
        suggested_series=suggested_series,
        show_day_filter=show_day_filter,
        game_days=game_days,
        fv_rows=fv_rows,
        fv_future_headers=fv_future_headers,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info("HTML generated", path=str(output_path), rows=len(rows))
