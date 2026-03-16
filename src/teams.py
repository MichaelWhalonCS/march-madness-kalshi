"""Tournament teams, seeds, regions, and name normalization.

This module defines the 68-team bracket for the 2026 NCAA Tournament.
Bracket data sourced from official NCAA bracket released on Selection Sunday,
March 15, 2026.

The kalshi_abbr field on each Team maps to the Kalshi market ticker suffix
(e.g. DUKE in KXNCAAMBGAME-26MAR19SIEDUKE-DUKE).
"""

from __future__ import annotations

from dataclasses import dataclass

# ── Round definitions ──────────────────────────────────────────────────────────

ROUNDS = ["R64", "R32", "S16", "E8", "F4", "Championship"]

ROUND_LABELS = {
    "R64": "Make R32",
    "R32": "Make S16",
    "S16": "Make E8",
    "E8": "Make F4",
    "F4": "Make Final",
    "Championship": "Win Title",
}


# ── Team dataclass ─────────────────────────────────────────────────────────────

@dataclass
class Team:
    name: str           # Display name, e.g. "Duke"
    seed: int           # 1-16
    region: str         # "East", "West", "South", "Midwest"
    kalshi_abbr: str = ""   # Kalshi ticker abbreviation (e.g. "DUKE")
    eliminated: bool = False
    kalshi_name: str = ""   # Kept for back-compat; unused


# ── 2026 Bracket ───────────────────────────────────────────────────────────────
# Real bracket from Selection Sunday, March 15, 2026.
# kalshi_abbr comes from the Kalshi market ticker suffix (KXNCAAMBGAME series).
# First Four teams are marked with (FF) in comments.

TEAMS: list[Team] = [
    # ── East Region (Washington, D.C.) ─────────────────────
    Team("Duke",             1, "East",    "DUKE"),
    Team("UConn",            2, "East",    "CONN"),
    Team("Michigan St.",     3, "East",    "MSU"),
    Team("Kansas",           4, "East",    "KU"),
    Team("St. John's",       5, "East",    "SJU"),
    Team("Louisville",       6, "East",    "LOU"),
    Team("UCLA",             7, "East",    "UCLA"),
    Team("Ohio St.",         8, "East",    "OSU"),
    Team("TCU",              9, "East",    "TCU"),
    Team("UCF",             10, "East",    "UCF"),
    Team("South Florida",   11, "East",    "USF"),
    Team("Northern Iowa",   12, "East",    "UNI"),
    Team("Cal Baptist",     13, "East",    "CBU"),
    Team("N. Dakota St.",   14, "East",    "NDSU"),
    Team("Furman",          15, "East",    "FUR"),
    Team("Siena",           16, "East",    "SIE"),

    # ── West Region (San Jose, CA) ─────────────────────────
    Team("Arizona",          1, "West",    "ARIZ"),
    Team("Purdue",           2, "West",    "PUR"),
    Team("Gonzaga",          3, "West",    "GONZ"),
    Team("Arkansas",         4, "West",    "ARK"),
    Team("Wisconsin",        5, "West",    "WIS"),
    Team("BYU",              6, "West",    ""),       # R64 opponent is FF winner
    Team("Miami (FL)",       7, "West",    "MIA"),
    Team("Villanova",        8, "West",    "VILL"),
    Team("Utah St.",         9, "West",    "USU"),
    Team("Missouri",        10, "West",    "MIZZ"),
    Team("Texas",           11, "West",    "TEX"),    # (FF) vs NC State
    Team("NC State",        11, "West",    "NCST"),   # (FF) vs Texas
    Team("High Point",      12, "West",    "HP"),
    Team("Hawai'i",         13, "West",    "HAW"),
    Team("Kennesaw St.",    14, "West",    "KENN"),
    Team("Queens",          15, "West",    "QUC"),
    Team("LIU",             16, "West",    "LIU"),

    # ── South Region (Houston, TX) ─────────────────────────
    Team("Florida",          1, "South",   ""),       # R64 opponent is FF winner
    Team("Houston",          2, "South",   "HOU"),
    Team("Illinois",         3, "South",   "ILL"),
    Team("Nebraska",         4, "South",   "NEB"),
    Team("Vanderbilt",       5, "South",   "VAN"),
    Team("North Carolina",   6, "South",   "UNC"),
    Team("Saint Mary's",     7, "South",   "SMC"),
    Team("Clemson",          8, "South",   "CLEM"),
    Team("Iowa",             9, "South",   "IOWA"),
    Team("Texas A&M",       10, "South",   "TXAM"),
    Team("VCU",             11, "South",   "VCU"),
    Team("McNeese",         12, "South",   "MCNS"),
    Team("Troy",            13, "South",   "TROY"),
    Team("Penn",            14, "South",   "PENN"),
    Team("Idaho",           15, "South",   "IDHO"),
    Team("Prairie View A&M",16, "South",   "PV"),    # (FF) vs Lehigh
    Team("Lehigh",          16, "South",   "LEH"),   # (FF) vs Prairie View A&M

    # ── Midwest Region (Chicago, IL) ───────────────────────
    Team("Michigan",         1, "Midwest", ""),       # R64 opponent is FF winner
    Team("Iowa St.",         2, "Midwest", "ISU"),
    Team("Virginia",         3, "Midwest", "UVA"),
    Team("Alabama",          4, "Midwest", "ALA"),
    Team("Texas Tech",       5, "Midwest", "TTU"),
    Team("Tennessee",        6, "Midwest", ""),       # R64 opponent is FF winner
    Team("Kentucky",         7, "Midwest", "UK"),
    Team("Georgia",          8, "Midwest", "UGA"),
    Team("Saint Louis",      9, "Midwest", "SLU"),
    Team("Santa Clara",     10, "Midwest", "SCU"),
    Team("Miami (OH)",      11, "Midwest", "MOH"),   # (FF) vs SMU
    Team("SMU",             11, "Midwest", "SMU"),   # (FF) vs Miami (OH)
    Team("Akron",           12, "Midwest", "AKR"),
    Team("Hofstra",         13, "Midwest", "HOF"),
    Team("Wright St.",      14, "Midwest", "WRST"),
    Team("Tennessee St.",   15, "Midwest", "TNST"),
    Team("UMBC",            16, "Midwest", "UMBC"),  # (FF) vs Howard
    Team("Howard",          16, "Midwest", "HOW"),   # (FF) vs UMBC
]

# ── Kalshi abbreviation → Team lookup ──────────────────────────────────────────
# Built at import time for fast lookups in odds.py.
KALSHI_ABBR_MAP: dict[str, Team] = {
    t.kalshi_abbr: t for t in TEAMS if t.kalshi_abbr
}

# ── Name aliases ───────────────────────────────────────────────────────────────
# Maps alternative names → canonical name for flexible lookups.

ALIASES: dict[str, str] = {
    "duke blue devils": "Duke",
    "north carolina": "North Carolina",
    "unc": "North Carolina",
    "tar heels": "North Carolina",
    "uconn": "UConn",
    "connecticut": "UConn",
    "st. john's": "St. John's",
    "saint john's": "St. John's",
    "iowa state": "Iowa St.",
    "iowa st": "Iowa St.",
    "texas a&m": "Texas A&M",
    "michigan state": "Michigan St.",
    "michigan st": "Michigan St.",
    "north dakota state": "N. Dakota St.",
    "north dakota st": "N. Dakota St.",
    "ndsu": "N. Dakota St.",
    "ohio state": "Ohio St.",
    "ohio st": "Ohio St.",
    "utah state": "Utah St.",
    "utah st": "Utah St.",
    "wright state": "Wright St.",
    "wright st": "Wright St.",
    "tennessee state": "Tennessee St.",
    "tennessee st": "Tennessee St.",
    "kennesaw state": "Kennesaw St.",
    "kennesaw st": "Kennesaw St.",
    "texas tech": "Texas Tech",
    "red raiders": "Texas Tech",
    "byu cougars": "BYU",
    "brigham young": "BYU",
    "st. mary's": "Saint Mary's",
    "saint mary's": "Saint Mary's",
    "california baptist": "Cal Baptist",
    "cal baptist": "Cal Baptist",
    "prairie view": "Prairie View A&M",
    "prairie view a&m": "Prairie View A&M",
    "miami fl": "Miami (FL)",
    "miami hurricanes": "Miami (FL)",
    "miami oh": "Miami (OH)",
    "miami redhawks": "Miami (OH)",
    "nc state": "NC State",
    "n.c. state": "NC State",
    "high point panthers": "High Point",
    "hawaii": "Hawai'i",
    "hawai'i": "Hawai'i",
    "long island": "LIU",
    "long island university": "LIU",
    "northern iowa panthers": "Northern Iowa",
    "south florida bulls": "South Florida",
    "usf": "South Florida",
}


# ── Lookup helpers ─────────────────────────────────────────────────────────────

def _build_lookup() -> dict[str, Team]:
    """Build a case-insensitive lookup dict: lowercase name or alias → Team."""
    lookup: dict[str, Team] = {}
    for team in TEAMS:
        lookup[team.name.lower()] = team
        if team.kalshi_abbr:
            lookup[team.kalshi_abbr.lower()] = team
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
