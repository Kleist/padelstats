"""Tests for importing the Google Sheet into the database."""

import copy

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.matches import db_matches
from app.models import Match, Player
from app.sheet_import import import_rows, verify
from padel.stats import build_stats, parse_matches
from tests.conftest import SAMPLE_ROWS


@pytest.fixture
def session(engine):
    with Session(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def rows():
    return copy.deepcopy(SAMPLE_ROWS)


def count(session, model):
    return session.scalar(select(func.count()).select_from(model))


def test_import_creates_matches_and_players(session, rows):
    report = import_rows(session, rows)
    assert (report.created, report.updated, report.deleted, report.skipped) == (9, 0, 0, [])
    assert count(session, Match) == 9
    assert count(session, Player) == 5
    first = session.scalar(select(Match).where(Match.sheet_row == 3))
    assert (first.played_on.isoformat(), first.venue, first.a1.name, first.b2.name) == (
        "2026-01-15", "Inde", "Anders", "Dennis"
    )
    assert [(s.games_a, s.games_b) for s in first.sets] == [(6, 3), (6, 0)]


def test_stats_from_database_equal_stats_from_sheet(session, rows):
    import_rows(session, rows)
    assert verify(session, rows) == []
    from_sheet, from_db = build_stats(parse_matches(rows)), build_stats(db_matches(session))
    for key in ("leaderboard", "elo", "pairs", "elo_dict", "pair_counts"):
        assert from_db[key] == from_sheet[key], key


def test_reimport_is_idempotent(session, rows):
    import_rows(session, rows)
    report = import_rows(session, rows)
    assert (report.created, report.updated, report.unchanged, report.deleted) == (0, 0, 9, 0)
    assert count(session, Match) == 9


def test_reimport_syncs_edits_additions_and_deletions(session, rows):
    import_rows(session, rows)
    rows[2][7] = "4"  # row 3: first set 6-3 → 6-4
    rows[3][2] = "Frede"  # row 4: new player
    rows.append(["30/04/2026", "Ude", "Anders", "Bo", "Carsten", "Dennis", "6", "2", "6", "2"])  # row 12
    report = import_rows(session, rows)
    assert (report.created, report.updated, report.unchanged, report.deleted) == (1, 2, 7, 0)
    assert count(session, Player) == 6

    del rows[4]  # row 5 deleted: rows below move up one
    report = import_rows(session, rows)
    assert (report.created, report.updated, report.unchanged, report.deleted) == (0, 7, 2, 1)
    assert count(session, Match) == 9
    assert verify(session, rows) == []
    assert session.scalar(select(Match).where(Match.sheet_row == 3)).sets[0].games_b == 4


def test_import_leaves_app_matches_alone(session, rows, logged_in):
    resp = logged_in.post("/ny", data={
        "played_on": "2026-10-09", "venue": "Ude",
        "a1": "Anders", "a2": "Bo", "b1": "Carsten", "b2": "Dennis", "s1a": "6", "s1b": "3",
    })
    assert resp.status_code == 200
    import_rows(session, rows)
    import_rows(session, rows[:5])  # rows deleted from the sheet are removed, the app match is kept
    assert count(session, Match) == 4
    assert len(db_matches(session)) == 4
    assert len(db_matches(session, imported_only=True)) == 3


def test_bad_rows_are_skipped_and_reported(session, rows):
    rows.append(["31/02/2026", "Ude", "Anders", "Bo", "Carsten", "Dennis", "6", "2"])
    rows.append(["01/05/2026", "Ude", "Anders", "Anders", "Carsten", "Dennis", "6", "2"])
    rows.append(["02/05/2026", "Ude", "Anders", "Bo", "Carsten", "Dennis", "6", "12"])
    rows.append(["short row"])
    report = import_rows(session, rows)
    assert report.skipped == [
        "row 12: unreadable date '31/02/2026'",
        "row 13: same player twice",
        "row 14: set score 6-12 out of range 0-7",
    ]
    assert count(session, Match) == 9
    assert verify(session, rows) == []


def test_verify_reports_differences(session, rows):
    import_rows(session, rows)
    session.scalar(select(Match).where(Match.sheet_row == 3)).sets[0].games_a = 2
    session.commit()
    differences = verify(session, rows)
    assert differences[0].startswith("match 1:")
    assert "leaderboard differs" in differences
