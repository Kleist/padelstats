"""The stats page must not let markup in player names through."""

from padel.render import render_html
from padel.stats import parse_matches

EVIL = "<img src=x onerror=alert(1)>"


def test_player_names_are_escaped():
    rows = [[], [], ["01/05/2026", "Inde", EVIL, "Bo", "Carsten", "</script><b>", "6", "2", "6", "3"]]
    html = render_html(parse_matches(rows))
    assert EVIL not in html
    assert "</script><b>" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html  # HTML tables
    assert "\\u003cimg src=x onerror=alert(1)\\u003e" in html  # JSON inside <script>
