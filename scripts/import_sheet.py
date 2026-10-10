#!/usr/bin/env python3
"""Import matches from the Google Sheet into the database (DATABASE_URL).

Safe to re-run: rows are matched by sheet row number, so changes in the sheet are synced and
matches entered in the app are left alone.

    poetry run python scripts/import_sheet.py            # import
    poetry run python scripts/import_sheet.py --dry-run  # show what would change, write nothing
"""

import argparse
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()  # before app.db reads DATABASE_URL

from app.db import SessionLocal  # noqa: E402
from app.sheet_import import import_rows  # noqa: E402
from build import fetch_data  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="roll back instead of committing")
    args = parser.parse_args()

    rows = fetch_data()
    print(f"Fetched {len(rows)} rows from the sheet")
    with SessionLocal() as session:
        if args.dry_run:
            session.commit = session.flush  # keep everything in the transaction, rolled back on close
        report = import_rows(session, rows)
        print(f"Import: {report.summary()}{' (dry run, nothing saved)' if args.dry_run else ''}")
        for reason in report.skipped:
            print(f"  skipped {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
