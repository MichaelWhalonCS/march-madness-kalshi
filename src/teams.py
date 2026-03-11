"""Tournament teams, seeds, regions, and name normalization.

This module defines the 68-team bracket for the 2026 NCAA Tournament.
Teams will be filled in once the bracket is announced (Selection Sunday, March 15, 2026).

The TEAMS list and ALIASES dict are the two things to update when the bracket drops.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── Round definitions ──────────────────────────────────────────────────────────

ROUNDS = ["R64", "R32", "S16", "E8", "F4", "Championship"]

ROUND_LABELS = {
    "R64": "R64→R32",
    "R32": "R32→S16",
    "S16": "S16→E8",
    "E8": "E8→F4",
    "F4": "F4→Final",
    "Championship": "Champ",
}


# ── Team dataclass ─────────────────────────────────────────────────────────────

@dataclass
class Team:
    name: str          # Display name, e.g. "Duke"
    seed: int          # 1-16
    region: str        # e.g. "East", "West", "South", "Midwest"
    eliminated: bool = False
    kalshi_name: str = ""  # Name as it appears in Kalshi markets (filled after discovery)


# ── 2026 Bracket ───────────────────────────────────────────────────────────────
# ⚠️  PLACEHOLDER — Replace with actual bracket after Selection Sunday (March 15, 2026).
#     Format: Team(name, seed, region)
#
#     Each region has seeds 1–16 (64 teams in main draw + 4 First Four).
#     First Four teams share a seed line (e.g. two 16-seeds in the same region).

TEAMS: list[Team] = [
    # ── East Region ────────────────────────────────────────
    Team("Duke", 1, "East"),
    Team("Alabama", 2, "East"),
    Team("Wisconsin", 3, "East"),
    Team("Arizona", 4, "East"),
    Team("Oregon", 5, "East"),
    Team("BYU", 6, "East"),
    Team("St. Mary's", 7, "East"),
    Team("Mississippi St.", 8, "East"),
    Team("Baylor", 9, "East"),
    Team("Vanderbilt", 10, "East"),
    Team("VCU", 11, "East"),
    Team("Liberty", 12, "East"),
    Team("Yale", 13, "East"),
    Team("Lipscomb", 14, "East"),
    Team("Robert Morris", 15, "East"),
    Team("American", 16, "East"),

    # ── West Region ────────────────────────────────────────
    Team("Houston", 1, "West"),
    Team("Tennessee", 2, "West"),
    Team("Kentucky", 3, "West"),
    Team("Purdue", 4, "West"),
    Team("Clemson", 5, "West"),
    Team("Illinois", 6, "West"),
    Team("UCLA", 7, "West"),
    Team("Gonzaga", 8, "West"),
    Team("Georgia", 9, "West"),
    Team("Texas Tech", 10, "West"),
    Team("Drake", 11, "West"),
    Team("McNeese", 12, "West"),
    Team("High Point", 13, "West"),
    Team("Troy", 14, "West"),
    Team("Montana", 15, "West"),
    Team("Norfolk St.", 16, "West"),

    # ── South Region ───────────────────────────────────────
    Team("Auburn", 1, "South"),
    Team("Iowa St.", 2, "South"),
    Team("Florida", 3, "South"),
    Team("Texas A&M", 4, "South"),
    Team("Michigan St.", 5, "South"),
    Team("Missouri", 6, "South"),
    Team("Marquette", 7, "South"),
    Team("Louisville", 8, "South"),
    Team("Creighton", 9, "South"),
    Team("New Mexico", 10, "South"),
    Team("San Diego St.", 11, "South"),
    Team("UC Irvine", 12, "South"),
    Team("Vermont", 13, "South"),
    Team("Grand Canyon", 14, "South"),
    Team("Colgate", 15, "South"),
    Team("Grambling", 16, "South"),

    # ── Midwest Region ─────────────────────────────────────
    Team("UConn", 1, "Midwest"),
    Team("St. John's", 2, "Midwest"),
    Team("Marquette", 3, "Midwest"),
    Team("North Carolina", 4, "Midwest"),
    Team("Memphis", 5, "Midwest"),
    Team("Ole Miss", 6, "Midwest"),
    Team("Kansas", 7, "Midwest"),
    Team("Pittsburgh", 8, "Midwest"),
    Team("Maryland", 9, "Midwest"),
    Team("Xavier", 10, "Midwest"),
    Team("Nebraska", 11, "Midwest"),
    Team("Colorado St.", 12, "Midwest"),
    Team("Akron", 13, "Midwest"),
    Team("Morehead St.", 14, "Midwest"),
    Team("Wofford", 15, "Midwest"),
    Team("FDU", 16, "Midwest"),
]

# ── Name aliases ───────────────────────────────────────────────────────────────
# Maps alternative names (Kalshi names, abbreviations, common variants) → canonical name.
# Canonical name = the `name` field in the Team dataclass above.
#
# ⚠️  Populate after running `scripts/discover_tickers.py` to see how Kalshi names teams.

ALIASES: dict[str, str] = {
    "duke blue devils": "Duke",
    "north carolina": "North Carolina",
    "unc": "North Carolina",
    "tar heels": "North Carolina",
    "uconn huskies": "UConn",
    "connecticut": "UConn",
    "st. john's": "St. John's",
    "saint john's": "St. John's",
    "iowa state": "Iowa St.",
    "texas a&m": "Texas A&M",
    "michigan state": "Michigan St.",
    "mississippi state": "Mississippi St.",
    "san diego state": "San Diego St.",
    "colorado state": "Colorado St.",
    "norfolk state": "Norfolk St.",
    "morehead state": "Morehead St.",
    "texas tech red raiders": "Texas Tech",
    "ole miss rebels": "Ole Miss",
    "mississippi": "Ole Miss",
    "byu cougars": "BYU",
    "brigham young": "BYU",
    "st. mary's gaels": "St. Mary's",
    "saint mary's": "St. Mary's",
    "uc irvine anteaters": "UC Irvine",
    "robert morris colonials": "Robert Morris",
    "fairleigh dickinson": "FDU",
}


# ── Lookup helpers ─────────────────────────────────────────────────────────────

def _build_lookup() -> dict[str, Team]:
    """Build a case-insensitive lookup dict: lowercase name or alias → Team."""
    lookup: dict[str, Team] = {}
    for team in TEAMS:
        lookup[team.name.lower()] = team
        if team.kalshi_name:
            lookup[team.kalshi_name.lower()] = team
    for alias, canonical in ALIASES.items():
        canon_lower = canonical.lower()
        if canon_lower in lookup:
            lookup[alias.lower()] = lookup[canon_lower]
    return lookup


_team_lookup: dict[str, Team] | None = None


def find_team(name: str) -> Team | None:
    """Look up a team by name (case-insensitive, alias-aware)."""
    global _team_lookup
    if _team_lookup is None:
        _team_lookup = _build_lookup()
    return _team_lookup.get(name.strip().lower())


def get_all_teams() -> list[Team]:
    """Return all tournament teams (including eliminated)."""
    return list(TEAMS)


def get_active_teams() -> list[Team]:
    """Return only teams that have not been eliminated."""
    return [t for t in TEAMS if not t.eliminated]
