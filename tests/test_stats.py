"""Tests for compute_player_stats()."""

from build import compute_player_stats


def _match(team_a, team_b, sets, winner):
    """Helper to build a minimal match dict."""
    sets_won_a = sum(1 for sa, sb in sets if sa > sb)
    sets_won_b = sum(1 for sa, sb in sets if sb > sa)
    games_a = sum(sa for sa, sb in sets)
    games_b = sum(sb for sa, sb in sets)
    return {
        "date": "01/01/2026", "date_sortable": "2026-01-01",
        "team_a": team_a, "team_b": team_b, "sets": sets,
        "sets_won": (sets_won_a, sets_won_b),
        "games": (games_a, games_b), "winner": winner,
    }


def test_empty():
    assert compute_player_stats([]) == []


def test_single_match_winner_stats():
    m = _match(["A", "B"], ["C", "D"], [(6, 3), (6, 0)], "A")
    lb = {p["name"]: p for p in compute_player_stats([m])}
    assert lb["A"]["matches_won"] == 1
    assert lb["A"]["matches_lost"] == 0
    assert lb["C"]["matches_won"] == 0
    assert lb["C"]["matches_lost"] == 1


def test_sets_and_games():
    m = _match(["A", "B"], ["C", "D"], [(6, 3), (4, 6), (6, 2)], "A")
    lb = {p["name"]: p for p in compute_player_stats([m])}
    assert lb["A"]["sets_won"] == 2
    assert lb["A"]["sets_lost"] == 1
    assert lb["A"]["games_won"] == 16
    assert lb["A"]["games_lost"] == 11
    assert lb["C"]["sets_won"] == 1
    assert lb["C"]["sets_lost"] == 2


def test_win_percentage():
    matches = [
        _match(["A", "B"], ["C", "D"], [(6, 3)], "A"),
        _match(["A", "B"], ["C", "D"], [(6, 3)], "A"),
        _match(["A", "B"], ["C", "D"], [(3, 6)], "B"),
    ]
    lb = {p["name"]: p for p in compute_player_stats(matches)}
    assert abs(lb["A"]["win_pct"] - 200 / 3) < 0.01  # 66.67%
    assert abs(lb["C"]["win_pct"] - 100 / 3) < 0.01  # 33.33%


def test_sorted_by_win_pct_then_wins():
    matches = [
        _match(["A", "B"], ["C", "D"], [(6, 3)], "A"),
        _match(["A", "B"], ["C", "D"], [(6, 3)], "A"),
        _match(["C", "D"], ["A", "B"], [(6, 3)], "C"),  # C wins once
    ]
    lb = compute_player_stats(matches)
    names = [p["name"] for p in lb]
    # A and B have 66.7%, C and D have 33.3%
    assert names.index("A") < names.index("C")
    assert names.index("B") < names.index("D")


def test_egg_counting():
    m = _match(["A", "B"], ["C", "D"], [(6, 0), (0, 6)], "draw")
    lb = {p["name"]: p for p in compute_player_stats([m])}
    assert lb["A"]["eggs_given"] == 1
    assert lb["A"]["eggs_received"] == 1
    assert lb["C"]["eggs_given"] == 1
    assert lb["C"]["eggs_received"] == 1


def test_streak_tracking():
    matches = [
        _match(["A", "B"], ["C", "D"], [(6, 3)], "A"),
        _match(["A", "B"], ["C", "D"], [(6, 3)], "A"),
        _match(["A", "B"], ["C", "D"], [(6, 3)], "A"),
        _match(["A", "B"], ["C", "D"], [(3, 6)], "B"),  # streak broken
        _match(["A", "B"], ["C", "D"], [(6, 3)], "A"),
    ]
    lb = {p["name"]: p for p in compute_player_stats(matches)}
    assert lb["A"]["best_streak"] == 3
    assert lb["A"]["current_win_streak"] == 1
    assert lb["A"]["current_lose_streak"] == 0


def test_draw_not_counted_as_win_or_loss():
    m = _match(["A", "B"], ["C", "D"], [(6, 3), (3, 6)], "draw")
    lb = {p["name"]: p for p in compute_player_stats([m])}
    assert lb["A"]["matches_played"] == 1
    assert lb["A"]["matches_won"] == 0
    assert lb["A"]["matches_lost"] == 0
