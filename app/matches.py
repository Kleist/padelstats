"""Matches from the database, in the shape the stats code (padel.stats) works with."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Match
from padel.stats import parse_row


def db_rows(session: Session):
    """All matches in the database as sheet-style rows, in the order the stats should process them.

    Sheet order is kept for imported matches; app-entered matches follow, by date.
    """
    query = select(Match).order_by(Match.sheet_row.is_(None), Match.sheet_row, Match.played_on, Match.id)
    rows = []
    for m in session.scalars(query).unique():
        scores = [str(v) for s in m.sets for v in (s.games_a, s.games_b)]
        rows.append([m.played_on.strftime("%d/%m/%Y"), m.venue, m.a1.name, m.a2.name, m.b1.name, m.b2.name, *scores])
    return rows


def db_matches(session: Session):
    """Match dicts (as from padel.stats.parse_matches) computed from the database."""
    return [parse_row(row) for row in db_rows(session)]
