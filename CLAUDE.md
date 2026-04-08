# CLAUDE.md

## Project overview

Padel stats static site generator. Fetches match data from Google Sheets, computes player statistics (leaderboard, Elo ratings, pair stats), and generates a single-page HTML site deployed to GitHub Pages.

## Architecture

- `build.py` — Python logic: data fetching, parsing, statistics computation, and HTML generation
- `templates/index.html` — Jinja2 template with inline CSS and vanilla JavaScript
- Output: `dist/index.html` — single self-contained HTML file (no external dependencies)

**Data flow:** Google Sheets API → `parse_matches()` → `compute_player_stats()` / `compute_elo()` / `compute_pair_stats()` → Jinja2 template → `dist/index.html`

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

# Run tests (39 tests: 1 acceptance + 38 unit)
poetry run pytest

# Run linter
poetry run ruff check .

# Update golden file after intentional output changes
python tests/update_golden.py
```

## Environment variables

Stored in `.env` (gitignored). Required:
- `GOOGLE_SHEETS_API_KEY` — Google Sheets API key
- `SPREADSHEET_ID` — ID of the spreadsheet with match data

## Deployment

- **Production:** GitHub Actions deploys to GitHub Pages on push to `main` and daily at 06:00 UTC (`.github/workflows/deploy.yml`)
- **PR preview:** Builds on pull requests and uploads artifact (`.github/workflows/preview.yml`)
- **CI checks:** Lint (ruff) → Tests (pytest) → Build, in both workflows

## Key conventions

- All HTML, CSS, and JS live in `templates/index.html` (Jinja2 template)
- The generated output is a single self-contained HTML file — no external JS/CSS dependencies
- Dark theme using CSS custom properties (see `:root` variables)
- Danish language for UI labels
- Tables support client-side sorting via `data-sort` attributes on `<td>` elements and `class="sortable"` on `<th>` elements
- Player names in tables are clickable links (`class="player-link"`) that toggle Elo chart display

## Testing

- **Acceptance test** (`tests/test_acceptance.py`): Generates HTML from dummy data and compares byte-for-byte to `tests/expected/index.html`. Catches any unintentional output changes.
- **Unit tests** (`tests/test_parse.py`, `tests/test_stats.py`, `tests/test_elo.py`, `tests/test_pairs.py`): Cover all pure computation functions.
- **Dummy data** (`tests/conftest.py`): 9 matches across 5 players covering wins, losses, draws, eggs, tiebreaks, unfinished sets, and streaks.
