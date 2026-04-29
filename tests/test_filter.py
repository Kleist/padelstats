"""Tests for filter_by_venue()."""

from build import filter_by_venue


def _m(sted, name="X"):
    return {"sted": sted, "team_a": [name], "team_b": [], "winner": "draw"}


MATCHES = [_m("Inde", "a"), _m("Ude", "b"), _m("Inde", "c"), _m("Ude", "d")]


def test_begge_returns_all():
    assert filter_by_venue(MATCHES, "begge") == MATCHES


def test_begge_returns_a_copy():
    out = filter_by_venue(MATCHES, "begge")
    out.clear()
    assert len(MATCHES) == 4


def test_inde_filters():
    out = filter_by_venue(MATCHES, "inde")
    assert [m["team_a"][0] for m in out] == ["a", "c"]


def test_ude_filters():
    out = filter_by_venue(MATCHES, "ude")
    assert [m["team_a"][0] for m in out] == ["b", "d"]


def test_unknown_venue_returns_empty():
    assert filter_by_venue(MATCHES, "tag") == []
