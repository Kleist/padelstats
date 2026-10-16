"""Import matches from the Google Sheet into the database, and check the result.

The import is idempotent: each sheet row is stored with its row number (``Match.sheet_row``), so
re-running it updates changed rows, adds new ones and removes rows deleted from the sheet.
Matches entered in the app (``sheet_row`` is NULL) are never touched.
"""

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import get_or_create_player
from app.matches import db_matches
from app.models import Match, MatchSet
from padel.stats import build_stats, parse_row

HEADER_ROWS = 2  # same as parse_matches


@dataclass
class ImportReport:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    skipped: list[str] = field(default_factory=list)  # human-readable reasons, one per bad row

    def summary(self):
        return (
            f"{self.created} new, {self.updated} updated, {self.unchanged} unchanged, "
            f"{self.deleted} deleted, {len(self.skipped)} skipped"
        )


def sheet_matches(rows):
    """Yield (sheet_row, match dict) for each match row. sheet_row is 1-based, as shown in Google Sheets."""
    for row_no, row in enumerate(rows[HEADER_ROWS:], start=HEADER_ROWS + 1):
        match = parse_row(row)
        if match is not None:
            yield row_no, match


def validate(match):
    """Return a reason the match can't be stored, or None."""
    try:
        date.fromisoformat(match["date_sortable"])
    except ValueError:
        return f"unreadable date {match['date']!r}"
    if len(match["sted"]) > 20:
        return f"venue {match['sted']!r} too long"
    names = match["team_a"] + match["team_b"]
    if any(not n for n in names):
        return "missing player name"
    if len({n.lower() for n in names}) < 4:
        return "same player twice"
    for a, b in match["sets"]:
        if not (0 <= a <= 7 and 0 <= b <= 7):
            return f"set score {a}-{b} out of range 0-7"
    return None


def match_key(m: Match):
    """Everything about a stored match that comes from the sheet, for change detection."""
    return (
        m.played_on, m.venue, m.a1.name, m.a2.name, m.b1.name, m.b2.name,
        tuple((s.games_a, s.games_b) for s in m.sets),
    )


def import_rows(session: Session, rows) -> ImportReport:
    """Sync the sheet rows into the database. Commits on success."""
    report = ImportReport()
    existing = {m.sheet_row: m for m in session.scalars(select(Match).where(Match.sheet_row.is_not(None))).unique()}
    seen = set()

    for row_no, data in sheet_matches(rows):
        reason = validate(data)
        if reason:
            report.skipped.append(f"row {row_no}: {reason}")
            continue
        seen.add(row_no)
        played_on = date.fromisoformat(data["date_sortable"])
        players = [get_or_create_player(session, n) for n in data["team_a"] + data["team_b"]]
        wanted = (played_on, data["sted"], *(p.name for p in players), tuple(data["sets"]))

        match = existing.get(row_no)
        if match is not None and match_key(match) == wanted:
            report.unchanged += 1
            continue
        if match is None:
            match = Match(sheet_row=row_no)
            session.add(match)
            report.created += 1
        else:
            report.updated += 1
        match.played_on = played_on
        match.venue = data["sted"]
        match.a1, match.a2, match.b1, match.b2 = players
        match.sets = []
        session.flush()  # delete old sets before inserting new ones with the same primary keys
        match.sets = [MatchSet(set_no=i, games_a=a, games_b=b) for i, (a, b) in enumerate(data["sets"], start=1)]

    for row_no, match in existing.items():
        if row_no not in seen:
            session.delete(match)
            report.deleted += 1

    session.commit()
    return report


def _comparable(stats):
    """Stats with the display-only date string removed (the sheet may format dates differently)."""
    stats["elo_history"] = {
        p: [{k: v for k, v in e.items() if k != "date"} for e in hist] for p, hist in stats["elo_history"].items()
    }
    return stats


def verify(session: Session, rows):
    """Compare stats from the sheet with stats from the imported matches. Returns a list of differences."""
    valid = [m for _, m in sheet_matches(rows) if validate(m) is None]
    from_db = db_matches(session, imported_only=True)
    differences = []
    if len(valid) != len(from_db):
        differences.append(f"sheet has {len(valid)} valid matches, database has {len(from_db)} imported")
    for i, (a, b) in enumerate(zip(valid, from_db)):
        a, b = dict(a, date=None), dict(b, date=None)
        if a != b:
            differences.append(f"match {i + 1}: sheet {a} != database {b}")
    sheet_stats, db_stats = _comparable(build_stats(valid)), _comparable(build_stats(from_db))
    for key in sheet_stats:
        if sheet_stats[key] != db_stats[key]:
            differences.append(f"{key} differs")
    return differences
