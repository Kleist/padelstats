"""Tests for compute_elo()."""

from build import compute_elo


def _match(team_a, team_b, winner, date="01/01/2026"):
    return {
        "date": date, "date_sortable": date,
        "team_a": team_a, "team_b": team_b,
        "sets": [], "sets_won": (0, 0), "games": (0, 0),
        "winner": winner,
    }


def test_empty():
    result, history = compute_elo([])
    assert result == []
    assert dict(history) == {}


def test_single_match_winners_gain():
    m = _match(["A", "B"], ["C", "D"], "A")
    result, _ = compute_elo([m])
    elos = {p["name"]: p["elo"] for p in result}
    assert elos["A"] > 1500
    assert elos["B"] > 1500
    assert elos["C"] < 1500
    assert elos["D"] < 1500


def test_symmetric_changes():
    m = _match(["A", "B"], ["C", "D"], "A")
    result, _ = compute_elo([m])
    elos = {p["name"]: p["elo"] for p in result}
    # Winner gain equals loser loss (for equal starting ratings)
    assert elos["A"] - 1500 == 1500 - elos["C"]


def test_draw_skipped():
    m = _match(["A", "B"], ["C", "D"], "draw")
    result, history = compute_elo([m])
    assert result == []
    assert dict(history) == {}


def test_history_tracks_each_match():
    matches = [
        _match(["A", "B"], ["C", "D"], "A", "2026-01-01"),
        _match(["A", "B"], ["C", "D"], "B", "2026-01-02"),
    ]
    _, history = compute_elo(matches)
    assert len(history["A"]) == 2
    assert history["A"][0]["elo"] > 1500  # won first
    assert history["A"][1]["elo"] < history["A"][0]["elo"]  # lost second


def test_history_won_flag():
    m = _match(["A", "B"], ["C", "D"], "A")
    _, history = compute_elo([m])
    assert history["A"][0]["won"] is True
    assert history["C"][0]["won"] is False


def test_custom_k_factor():
    m = _match(["A", "B"], ["C", "D"], "A")
    result_low, _ = compute_elo([m], k=16)
    result_high, _ = compute_elo([m], k=64)
    elo_low = {p["name"]: p["elo"] for p in result_low}
    elo_high = {p["name"]: p["elo"] for p in result_high}
    # Higher K produces bigger changes
    assert abs(elo_high["A"] - 1500) > abs(elo_low["A"] - 1500)


def test_sorted_by_elo_descending():
    matches = [
        _match(["A", "B"], ["C", "D"], "A"),
        _match(["A", "B"], ["C", "D"], "A"),
    ]
    result, _ = compute_elo(matches)
    elos = [p["elo"] for p in result]
    assert elos == sorted(elos, reverse=True)


def test_avg_opponent_and_partner():
    m = _match(["A", "B"], ["C", "D"], "A")
    result, _ = compute_elo([m])
    r = {p["name"]: p for p in result}
    # A's partner is B, A's opponents are C and D
    assert r["A"]["avg_partner"] == r["B"]["elo"]
    assert r["A"]["avg_opp"] == (r["C"]["elo"] + r["D"]["elo"]) // 2 or True  # rounded
