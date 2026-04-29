"""Acceptance test: generate HTML from dummy data and compare to golden file."""

from pathlib import Path

from build import render_html

GOLDEN_FILE = Path(__file__).parent / "expected" / "index.html"


def render_site(matches):
    """Render the site HTML from match data, exactly like main() does."""
    return render_html(matches)


def test_generated_html_matches_golden_file(sample_matches):
    html = render_site(sample_matches)
    expected = GOLDEN_FILE.read_text()
    assert html == expected, (
        "Generated HTML differs from golden file. "
        "If the change is intentional, run: python tests/update_golden.py"
    )
