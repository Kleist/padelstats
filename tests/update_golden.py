#!/usr/bin/env python3
"""Regenerate the golden file from dummy data.

Run this when you intentionally change the HTML output:
    python tests/update_golden.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.conftest import SAMPLE_ROWS
from tests.test_acceptance import render_site
from build import parse_matches

matches = parse_matches(SAMPLE_ROWS)
html = render_site(matches)

golden = Path(__file__).parent / "expected" / "index.html"
golden.write_text(html)
print(f"Updated {golden} ({len(html)} bytes)")
