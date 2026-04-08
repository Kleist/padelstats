"""Acceptance test: generate HTML from dummy data and compare to golden file."""

import json
from pathlib import Path

from build import TEMPLATE, compute_elo, compute_pair_stats, compute_player_stats

GOLDEN_FILE = Path(__file__).parent / "expected" / "index.html"


def render_site(matches):
    """Render the site HTML from match data, exactly like main() does."""
    leaderboard = compute_player_stats(matches)
    elo, elo_history = compute_elo(matches)
    pairs = compute_pair_stats(matches)

    elo_dict = {p["name"]: p["elo"] for p in elo}
    pair_counts = {p["players"]: p["played"] for p in pairs}

    return TEMPLATE.render(
        matches=matches,
        leaderboard=leaderboard,
        elo=elo,
        elo_json=json.dumps(elo_dict),
        pair_counts_json=json.dumps(pair_counts),
        elo_history_json=json.dumps(dict(elo_history)),
        pairs=pairs,
    )


def test_generated_html_matches_golden_file(sample_matches):
    html = render_site(sample_matches)
    expected = GOLDEN_FILE.read_text()
    assert html == expected, (
        "Generated HTML differs from golden file. "
        "If the change is intentional, run: python tests/update_golden.py"
    )
