"""Tests for the ESPN BPI module."""

from src.espn_bpi import _ESPN_IDX_TO_ROUND, _match_espn_team


def test_match_espn_team_by_nickname():
    """Direct nickname match."""
    assert _match_espn_team("Duke", "DUKE", "Duke Blue Devils") == "Duke"
    assert _match_espn_team("UConn", "CONN", "UConn Huskies") == "UConn"
    assert _match_espn_team("Kansas", "KU", "Kansas Jayhawks") == "Kansas"


def test_match_espn_team_by_alias():
    """Nickname that needs alias mapping (ESPN drops periods)."""
    assert _match_espn_team("Michigan St", "MSU", "Michigan State Spartans") == "Michigan St."
    assert _match_espn_team("Iowa St", "ISU", "Iowa State Cyclones") == "Iowa St."
    assert _match_espn_team("Ohio St", "OSU", "Ohio State Buckeyes") == "Ohio St."


def test_match_espn_team_unknown():
    """Unknown team returns None."""
    assert _match_espn_team("FakeTeam", "FAKE", "Fake Team FakeTeam") is None


def test_espn_idx_mapping():
    """Verify index-to-round mapping covers all expected rounds."""
    rounds = set(_ESPN_IDX_TO_ROUND.values())
    assert rounds == {"R64", "R32", "S16", "E8", "F4", "Championship"}
