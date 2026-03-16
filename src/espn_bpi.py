"""Fetch ESPN BPI tournament advancement probabilities.

ESPN's internal API provides round-by-round advancement probabilities for all
68 tournament teams.  We map them to our round codes:

    ESPN column        →  Our round_probs key
    ─────────────────────────────────────────
    Rd of 32           →  R64   (prob of winning R64 game)
    Sweet 16           →  R32   (prob of reaching Sweet 16 = winning through R32)
    Elite 8            →  S16
    Final Four         →  E8
    Champ Gm           →  F4
    Title Win          →  Championship

Values come back as percentages (0–100); we convert to 0.0–1.0.
"""

from __future__ import annotations

import json
import urllib.request

import structlog

from .teams import find_team

logger = structlog.get_logger()

BPI_URL = (
    "https://site.web.api.espn.com/apis/fitt/v3/sports/basketball/"
    "mens-college-basketball/powerindex"
    "?view=tournament&limit=400&region=us&lang=en"
)

# Indices into the tournament category `values` list.
# Order: [seed, seedActual, region, titleWin, champGm, finalFour, elite8, sweet16, rd32]
#          0     1           2       3         4        5          6       7        8
_ESPN_IDX_TO_ROUND: dict[int, str] = {
    8: "R64",            # "Rd of 32"  → chance to win R64 game
    7: "R32",            # "Sweet 16"  → chance to reach Sweet 16
    6: "S16",            # "Elite 8"   → chance to reach Elite 8
    5: "E8",             # "Final Four" → chance to reach Final Four
    4: "F4",             # "Champ Gm"  → chance to reach championship game
    3: "Championship",   # "Title Win" → chance to win it all
}

# Extra aliases so ESPN nicknames match our team names
_ESPN_EXTRA_ALIASES: dict[str, str] = {
    "michigan st": "Michigan St.",
    "michigan st.": "Michigan St.",
    "ohio st": "Ohio St.",
    "ohio st.": "Ohio St.",
    "iowa st": "Iowa St.",
    "iowa st.": "Iowa St.",
    "utah st": "Utah St.",
    "utah st.": "Utah St.",
    "wright st": "Wright St.",
    "wright st.": "Wright St.",
    "tennessee st": "Tennessee St.",
    "tennessee st.": "Tennessee St.",
    "kennesaw st": "Kennesaw St.",
    "kennesaw st.": "Kennesaw St.",
    "n. dakota st": "N. Dakota St.",
    "n. dakota st.": "N. Dakota St.",
    "north dakota st": "N. Dakota St.",
    "san diego st": "San Diego St.",
    "florida st": "Florida St.",
    "saint mary's": "Saint Mary's",
    "st. john's": "St. John's",
    "cal baptist": "Cal Baptist",
    "california baptist": "Cal Baptist",
    "prairie view": "Prairie View A&M",
    "prairie view a&m": "Prairie View A&M",
    "hawai'i": "Hawai'i",
    "hawaii": "Hawai'i",
    "miami (oh)": "Miami (OH)",
    "miami (fl)": "Miami (FL)",
    "south florida": "South Florida",
    "long island": "LIU",
    "long island university": "LIU",
}


def _match_espn_team(nickname: str, abbreviation: str, display_name: str) -> str | None:
    """Try to match an ESPN team entry to one of our team names.

    Attempts several strategies in order:
    1. find_team(nickname)       — handles most cases ("Duke", "UConn", etc.)
    2. find_team(abbreviation)   — catches kalshi_abbr matches
    3. find_team(display_name)   — "Duke Blue Devils" → probably no match, but try
    4. _ESPN_EXTRA_ALIASES       — handles "Michigan St" → "Michigan St." etc.
    """
    for candidate in [nickname, abbreviation, display_name]:
        team = find_team(candidate)
        if team:
            return team.name

    # Check extra aliases
    nick_lower = nickname.lower().strip()
    if nick_lower in _ESPN_EXTRA_ALIASES:
        return _ESPN_EXTRA_ALIASES[nick_lower]

    return None


def fetch_bpi() -> dict[str, dict[str, float]]:
    """Fetch ESPN BPI tournament data and return round probabilities per team.

    Returns:
        dict mapping team_name → {round_code → probability (0.0–1.0)}
        e.g. {"Duke": {"R64": 0.99, "R32": 0.917, "S16": 0.748, ...}, ...}
    """
    logger.info("Fetching ESPN BPI tournament data")

    try:
        req = urllib.request.Request(BPI_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception:
        logger.exception("Failed to fetch ESPN BPI data")
        return {}

    teams_data = data.get("teams", [])
    logger.info("ESPN BPI response", teams_count=len(teams_data))

    result: dict[str, dict[str, float]] = {}
    matched = 0
    unmatched: list[str] = []

    for entry in teams_data:
        team_info = entry.get("team", {})
        nickname = team_info.get("nickname", "")
        abbreviation = team_info.get("abbreviation", "")
        display_name = team_info.get("displayName", "")

        team_name = _match_espn_team(nickname, abbreviation, display_name)
        if not team_name:
            unmatched.append(f"{nickname} ({abbreviation})")
            continue

        # Find the tournament category
        categories = entry.get("categories", [])
        tourney_cat = None
        for cat in categories:
            if cat.get("name") == "tournament":
                tourney_cat = cat
                break

        if not tourney_cat:
            continue

        values = tourney_cat.get("values", [])
        if not values or len(values) < 9:
            # Team not in tournament bracket (values are all null)
            continue

        # Check if this team has actual tournament data (non-null probabilities)
        if values[3] is None and values[8] is None:
            continue

        round_probs: dict[str, float] = {}
        for idx, round_code in _ESPN_IDX_TO_ROUND.items():
            val = values[idx] if idx < len(values) else None
            if val is not None:
                round_probs[round_code] = val / 100.0  # Convert percentage → probability
            # If None, we simply omit that round

        if round_probs:
            result[team_name] = round_probs
            matched += 1

    logger.info(
        "ESPN BPI parsing complete",
        matched=matched,
        unmatched=len(unmatched),
        unmatched_teams=unmatched[:10] if unmatched else [],
    )
    return result
