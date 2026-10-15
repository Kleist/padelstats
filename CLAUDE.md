# CLAUDE.md

## Project overview

Padel stats static site generator. Fetches match data from Google Sheets, computes player statistics (leaderboard, Elo ratings, pair stats), and generates a single-page HTML site deployed to GitHub Pages.

A web app (`app/`) backed by Postgres is being built to replace the Sheet: players enter results from their phone. See `docs/PLAN.md` for the roadmap and `docs/SETUP.md` for hosting setup.

## Architecture

- `build.py` — static site build: fetches the Google Sheet and writes `dist/index.html`
- `padel/stats.py` — parsing and statistics (leaderboard, Elo, pairs), shared by `build.py` and the web app
- `padel/render.py` — renders `templates/index.html` from match dicts (`render_html()`)
- `templates/index.html` — Jinja2 template with inline CSS and vanilla JavaScript
- Output: `dist/index.html` — single self-contained HTML file (no external dependencies)

**Data flow:** Google Sheets API → `parse_matches()` → `compute_player_stats()` / `compute_elo()` / `compute_pair_stats()` → Jinja2 template → `dist/index.html`

### Web app (`app/`)

- FastAPI + Jinja2 (server-rendered, no JS build), SQLAlchemy 2.0 models in `app/models.py`, routes in `app/main.py`, templates in `app/templates/`
- Database: Postgres (Neon) in production via `DATABASE_URL`; defaults to SQLite `padelstats.db` locally
- Schema changes: edit `app/models.py` **and** add a migration in `migrations/versions/` (CI runs `alembic check` to catch drift)
- Login: shared `ADMIN_PASSWORD` → signed session cookie (`SESSION_SECRET`); `COOKIE_SECURE=0` for plain-http local runs
- Hosting: Fly.io (`fly.toml`, `Dockerfile`); migrations run as Fly `release_command`
- Sheet import: `app/sheet_import.py` + `scripts/import_sheet.py` (idempotent via `matches.sheet_row`, verifies stats DB == Sheet); run via the manual **Import from Google Sheet** workflow (`.github/workflows/import.yml`)
- Backups: nightly `pg_dump` artifact (`.github/workflows/backup.yml`)

## Build & run

```bash
# Install dependencies (requires Poetry)
poetry install --no-root

# Build the site (requires .env with GOOGLE_SHEETS_API_KEY and SPREADSHEET_ID)
poetry run python build.py
# Output: dist/index.html
```

## Test & lint

```bash
# Install dev dependencies
poetry install --no-root --extras dev

# Run tests (SQLite by default; set TEST_DATABASE_URL=postgresql://... to run app tests on Postgres)
poetry run pytest

# Run linter
poetry run ruff check .

# Update golden file after intentional output changes
python tests/update_golden.py

# Run the web app locally
COOKIE_SECURE=0 ADMIN_PASSWORD=test poetry run alembic upgrade head
COOKIE_SECURE=0 ADMIN_PASSWORD=test poetry run uvicorn app.main:app --reload

# Import the Google Sheet into DATABASE_URL (needs the .env sheet variables); --dry-run writes nothing
poetry run python scripts/import_sheet.py --dry-run

# New migration after changing app/models.py
poetry run alembic revision --autogenerate -m "describe change"
```

## Environment variables

Stored in `.env` (gitignored). Required for the static build:
- `GOOGLE_SHEETS_API_KEY` — Google Sheets API key
- `SPREADSHEET_ID` — ID of the spreadsheet with match data

Web app (GitHub secrets, synced to Fly by the deploy workflow): `DATABASE_URL`, `ADMIN_PASSWORD`, `FLY_API_TOKEN`, optionally `STAGING_DATABASE_URL`. `SESSION_SECRET` is generated on Fly on first deploy.

## Deployment

- **Production:** GitHub Actions deploys to GitHub Pages on push to `main` and daily at 06:00 UTC (`.github/workflows/deploy.yml`)
- **PR preview:** Builds on pull requests and uploads artifact (`.github/workflows/preview.yml`)
- **CI checks:** Lint (ruff) → Tests (pytest) → Build, in both workflows
- **Web app:** `.github/workflows/app.yml` — lint → tests on Postgres → `alembic check` on every PR; on `main` deploys to Fly.io (`padelstats-kleist`), and on same-repo PRs to the shared staging app `padelstats-kleist-staging` (separate DB via `STAGING_DATABASE_URL`, wiped and restored from the latest nightly backup on each deploy, which tests the backups); both smoke-test `/healthz/db` for the new commit SHA. Deploys are skipped (with a warning) until `FLY_API_TOKEN` (and for staging `STAGING_DATABASE_URL`) is set.

## Commits & pull requests

- Commit in small, logical, atomic chunks: one concern per commit, with a message saying what changed and why.
- Order commits refactor first, then schema/migrations, then the feature, then its workflows/automation, then docs/plan status.
- Each commit must pass `ruff check .` and `pytest` on its own. Check before pushing with `git rebase origin/main --exec 'poetry run ruff check . && poetry run pytest -q'`.
- Docs that describe a piece of work (`CLAUDE.md`, `docs/SETUP.md`) go in the same commit as that work. Marking a phase in `docs/PLAN.md` as done gets its own commit at the end.
- Keep a PR's history clean, also after the PR is open: fold fixes into the commit they belong to (amend/fixup, split, reorder, drop) and `git push --force-with-lease`. Don't add "fix previous commit" or revert-of-own-commit commits.
- Never rewrite `main`. For stacked PRs, rebase the stacked branch onto its rewritten base and force-push it too.

## Key conventions

- All HTML, CSS, and JS live in `templates/index.html` (Jinja2 template)
- The generated output is a single self-contained HTML file — no external JS/CSS dependencies
- Dark theme using CSS custom properties (see `:root` variables)
- Danish language for UI labels
- Tables support client-side sorting via `data-sort` attributes on `<td>` elements and `class="sortable"` on `<th>` elements
- Player names in tables are clickable links (`class="player-link"`) that toggle Elo chart display

## Testing

- **Acceptance test** (`tests/test_acceptance.py`): Generates HTML from dummy data and compares byte-for-byte to `tests/expected/index.html`. Catches any unintentional output changes.
- **App tests** (`tests/app/`): run the real Alembic migrations on a fresh DB, then exercise routes via FastAPI's TestClient.
- **Unit tests** (`tests/test_parse.py`, `tests/test_stats.py`, `tests/test_elo.py`, `tests/test_pairs.py`): Cover all pure computation functions.
- **Dummy data** (`tests/conftest.py`): 9 matches across 5 players covering wins, losses, draws, eggs, tiebreaks, unfinished sets, and streaks.
