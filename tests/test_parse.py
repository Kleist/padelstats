"""Tests for parse_matches()."""

from build import parse_matches


def test_empty_rows():
    assert parse_matches([]) == []


def test_header_rows_only():
    assert parse_matches([["header"], ["subheader"]]) == []


def test_short_rows_skipped():
    rows = [[], [], ["date", "sted", "a1", "a2", "b1", "b2"]]  # only 6 cols, need 8
    assert parse_matches(rows) == []


def test_single_match():
    rows = [[], [], ["15/01/2026", "Inde", "Anders", "Bo", "Carsten", "Dennis", "6", "3", "6", "0"]]
    result = parse_matches(rows)
    assert len(result) == 1
    m = result[0]
    assert m["team_a"] == ["Anders", "Bo"]
    assert m["team_b"] == ["Carsten", "Dennis"]
    assert m["sets"] == [(6, 3), (6, 0)]
    assert m["sets_won"] == (2, 0)
    assert m["games"] == (12, 3)
    assert m["winner"] == "A"


def test_team_b_wins():
    rows = [[], [], ["01/01/2026", "Inde", "A1", "A2", "B1", "B2", "3", "6", "0", "6"]]
    result = parse_matches(rows)
    assert result[0]["winner"] == "B"
    assert result[0]["sets_won"] == (0, 2)


def test_draw():
    rows = [[], [], ["01/01/2026", "Inde", "A1", "A2", "B1", "B2", "6", "3", "3", "6"]]
    result = parse_matches(rows)
    assert result[0]["winner"] == "draw"
    assert result[0]["sets_won"] == (1, 1)


def test_tiebreak_set():
    rows = [[], [], ["01/01/2026", "Inde", "A1", "A2", "B1", "B2", "7", "5"]]
    result = parse_matches(rows)
    assert result[0]["sets"] == [(7, 5)]
    assert result[0]["sets_won"] == (1, 0)
    assert result[0]["winner"] == "A"


def test_three_set_match():
    rows = [[], [], ["01/01/2026", "Inde", "A1", "A2", "B1", "B2", "6", "4", "3", "6", "6", "2"]]
    result = parse_matches(rows)
    m = result[0]
    assert len(m["sets"]) == 3
    assert m["sets_won"] == (2, 1)
    assert m["games"] == (15, 12)
    assert m["winner"] == "A"


def test_date_slash_format():
    rows = [[], [], ["15/01/2026", "Inde", "A1", "A2", "B1", "B2", "6", "3", "6", "0"]]
    assert parse_matches(rows)[0]["date_sortable"] == "2026-01-15"


def test_date_dash_format():
    rows = [[], [], ["15-01-2026", "Inde", "A1", "A2", "B1", "B2", "6", "3", "6", "0"]]
    assert parse_matches(rows)[0]["date_sortable"] == "2026-01-15"


def test_date_dot_format():
    rows = [[], [], ["15.01.2026", "Inde", "A1", "A2", "B1", "B2", "6", "3", "6", "0"]]
    assert parse_matches(rows)[0]["date_sortable"] == "2026-01-15"


def test_player_names_stripped():
    rows = [[], [], ["01/01/2026", "Inde", " Anders ", " Bo ", " Carsten ", " Dennis ", "6", "3", "6", "0"]]
    m = parse_matches(rows)[0]
    assert m["team_a"] == ["Anders", "Bo"]
    assert m["team_b"] == ["Carsten", "Dennis"]


def test_egg_set():
    """A 6-0 set is valid and counted."""
    rows = [[], [], ["01/01/2026", "Inde", "A1", "A2", "B1", "B2", "6", "0", "6", "0"]]
    m = parse_matches(rows)[0]
    assert m["sets"] == [(6, 0), (6, 0)]
    assert m["games"] == (12, 0)


def test_unfinished_set():
    """A set like 4-3 (neither reached 6/7) is parsed but not counted as won."""
    rows = [[], [], ["01/01/2026", "Inde", "A1", "A2", "B1", "B2", "6", "4", "4", "6", "4", "3"]]
    m = parse_matches(rows)[0]
    assert m["sets"] == [(6, 4), (4, 6), (4, 3)]
    assert m["sets_won"] == (1, 1)  # third set not won by either
    assert m["winner"] == "draw"
    assert m["games"] == (14, 13)


def test_multiple_matches():
    rows = [
        [], [],
        ["01/01/2026", "Inde", "A1", "A2", "B1", "B2", "6", "3", "6", "0"],
        ["02/01/2026", "Inde", "C1", "C2", "D1", "D2", "3", "6", "6", "3", "6", "4"],
    ]
    result = parse_matches(rows)
    assert len(result) == 2
    assert result[0]["date"] == "01/01/2026"
    assert result[1]["date"] == "02/01/2026"


def test_sted_column_ignored():
    """The 'Sted' column is accepted but not stored on the match dict."""
    rows = [[], [], ["01/01/2026", "Centerbanen", "A1", "A2", "B1", "B2", "6", "3", "6", "0"]]
    m = parse_matches(rows)[0]
    assert "sted" not in m
    assert m["team_a"] == ["A1", "A2"]
    assert m["sets"] == [(6, 3), (6, 0)]
