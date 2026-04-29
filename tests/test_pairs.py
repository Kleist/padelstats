"""Tests for compute_pair_stats()."""

from build import compute_pair_stats


def _match(team_a, team_b, winner):
    return {
        "date": "01/01/2026", "date_sortable": "2026-01-01",
        "team_a": team_a, "team_b": team_b,
        "sets": [], "sets_won": (0, 0), "games": (0, 0),
        "winner": winner,
    }


def test_empty():
    assert compute_pair_stats([]) == []


def test_single_match():
    m = _match(["A", "B"], ["C", "D"], "A")
    pairs = {p["players"]: p for p in compute_pair_stats([m])}
    assert pairs["A & B"]["played"] == 1
    assert pairs["A & B"]["won"] == 1
    assert pairs["A & B"]["lost"] == 0
    assert pairs["C & D"]["played"] == 1
    assert pairs["C & D"]["won"] == 0
    assert pairs["C & D"]["lost"] == 1


def test_pair_normalization():
    """[B, A] and [A, B] should be the same pair."""
    matches = [
        _match(["B", "A"], ["C", "D"], "A"),
        _match(["A", "B"], ["C", "D"], "A"),
    ]
    pairs = {p["players"]: p for p in compute_pair_stats(matches)}
    assert pairs["A & B"]["played"] == 2
    assert pairs["A & B"]["won"] == 2


def test_win_percentage():
    matches = [
        _match(["A", "B"], ["C", "D"], "A"),
        _match(["A", "B"], ["C", "D"], "A"),
        _match(["A", "B"], ["C", "D"], "B"),
    ]
    pairs = {p["players"]: p for p in compute_pair_stats(matches)}
    assert abs(pairs["A & B"]["win_pct"] - 200 / 3) < 0.01


def test_sorted_by_win_pct():
    matches = [
        _match(["A", "B"], ["C", "D"], "A"),
        _match(["A", "B"], ["C", "D"], "A"),
        _match(["C", "D"], ["E", "F"], "C"),
    ]
    result = compute_pair_stats(matches)
    pcts = [p["win_pct"] for p in result]
    assert pcts == sorted(pcts, reverse=True)


def test_draw_counted_in_played_not_won_lost():
    m = _match(["A", "B"], ["C", "D"], "draw")
    pairs = {p["players"]: p for p in compute_pair_stats([m])}
    assert pairs["A & B"]["played"] == 1
    assert pairs["A & B"]["won"] == 0
    assert pairs["A & B"]["lost"] == 0
    assert pairs["A & B"]["drawn"] == 1
    assert pairs["C & D"]["drawn"] == 1
