"""Shared test fixtures with dummy match data covering all features."""

import pytest

# Raw sheet rows matching the Google Sheets format: [date, sted, a1, a2, b1, b2, s1a, s1b, s2a, s2b, ...]
# Two header rows are skipped by parse_matches, so we include them.
SAMPLE_ROWS = [
    ["Dato", "Sted", "Hold A1", "Hold A2", "Hold B1", "Hold B2", "Sæt 1A", "Sæt 1B"],
    ["", "", "", "", "", "", "", ""],
    # Match 1: Anders & Bo beat Carsten & Dennis 2-0 (includes a 6-0 egg)
    ["15/01/2026", "Inde", "Anders", "Bo", "Carsten", "Dennis", "6", "3", "6", "0"],
    # Match 2: Anders & Carsten beat Bo & Erik 2-0
    ["22/01/2026", "Inde", "Anders", "Carsten", "Bo", "Erik", "6", "4", "6", "3"],
    # Match 3: Anders & Erik beat Bo & Dennis 2-1 (team B wins first set)
    ["05/02/2026", "Inde", "Bo", "Dennis", "Anders", "Erik", "6", "4", "3", "6", "2", "6"],
    # Match 4: Carsten & Erik beat Anders & Dennis 2-0 (includes a 6-0 egg)
    ["12/02/2026", "Inde", "Carsten", "Erik", "Anders", "Dennis", "6", "1", "6", "0"],
    # Match 5: Anders & Bo beat Dennis & Erik 2-1 (tiebreak set 7-5)
    ["26/02/2026", "Inde", "Anders", "Bo", "Dennis", "Erik", "6", "4", "3", "6", "7", "5"],
    # Match 6: Carsten & Bo beat Anders & Dennis 2-1
    ["05/03/2026", "Inde", "Carsten", "Bo", "Anders", "Dennis", "4", "6", "6", "2", "6", "4"],
    # Match 7: Anders & Erik beat Bo & Carsten 2-0
    ["19/03/2026", "Inde", "Anders", "Erik", "Bo", "Carsten", "6", "3", "6", "4"],
    # Match 8: Draw — equal sets won (1-1, no third set decided)
    ["02/04/2026", "Inde", "Anders", "Bo", "Carsten", "Erik", "6", "3", "3", "6"],
    # Match 9: Unfinished third set (4-3) — match abandoned mid-set
    ["16/04/2026", "Inde", "Bo", "Erik", "Anders", "Carsten", "6", "4", "4", "6", "4", "3"],
]


@pytest.fixture
def sample_rows():
    """Raw sheet rows including 2 header rows."""
    return SAMPLE_ROWS


@pytest.fixture
def sample_matches():
    """Parsed match dicts from sample rows."""
    from build import parse_matches
    return parse_matches(SAMPLE_ROWS)
