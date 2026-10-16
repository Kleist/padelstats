"""Tests for filter_matches()."""

from padel.stats import filter_matches


def _m(date_sortable, sted, a, b):
    return {"date_sortable": date_sortable, "sted": sted, "team_a": a, "team_b": b}


M1 = _m("2025-11-02", "Inde", ["Anders", "Bo"], ["Carsten", "Dennis"])
M2 = _m("2026-01-15", "Ude", ["Anders", "Carsten"], ["Bo", "Erik"])
M3 = _m("2026-03-05", "Inde", ["Bo", "Dennis"], ["Anders", "Erik"])
MATCHES = [M1, M2, M3]


def test_no_filters_returns_all_as_a_copy():
    out = filter_matches(MATCHES)
    assert out == MATCHES
    out.clear()
    assert len(MATCHES) == 3


def test_months():
    assert filter_matches(MATCHES, months=["2026-01"]) == [M2]
    assert filter_matches(MATCHES, months=["2025-01"]) == []


def test_several_months_means_any_of_them():
    assert filter_matches(MATCHES, months=["2025-11", "2026-03"]) == [M1, M3]


def test_venues():
    assert filter_matches(MATCHES, venues=["Inde"]) == [M1, M3]
    assert filter_matches(MATCHES, venues=["Ude"]) == [M2]
    assert filter_matches(MATCHES, venues=["Inde", "Ude"]) == MATCHES


def test_one_player_on_either_team():
    assert filter_matches(MATCHES, players=["Erik"]) == [M2, M3]


def test_all_selected_players_must_have_played():
    assert filter_matches(MATCHES, players=["Anders", "Bo"]) == MATCHES
    assert filter_matches(MATCHES, players=["Carsten", "Dennis"]) == [M1]
    assert filter_matches(MATCHES, players=["Anders", "Bo", "Carsten", "Dennis"]) == [M1]


def test_filters_combine():
    assert filter_matches(MATCHES, months=["2026-01", "2026-03"], venues=["Inde"], players=["Erik"]) == [M3]
