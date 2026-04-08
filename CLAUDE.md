# CLAUDE.md

## Project overview

Padel stats static site generator. Fetches match data from Google Sheets, computes player statistics (leaderboard, Elo ratings, pair stats), and generates a single-page HTML site deployed to GitHub Pages.

## Architecture

Single-file project: `build.py` contains all Python logic and an inline Jinja2 template with HTML, CSS, and vanilla JavaScript. No frontend framework or build tooling.

**Data flow:** Google Sheets API → `parse_matches()` → `compute_player_stats()` / `compute_elo()` / `compute_pair_stats()` → Jinja2 template → `dist/index.html`

## Build & run

```bash
# Install dependencies (requires Poetry)
poetry install --no-root

# Build the site (requires .env with GOOGLE_SHEETS_API_KEY and SPREADSHEET_ID)
poetry run python build.py
# Output: dist/index.html
```

## Environment variables

Stored in `.env` (gitignored). Required:
- `GOOGLE_SHEETS_API_KEY` — Google Sheets API key
- `SPREADSHEET_ID` — ID of the spreadsheet with match data

## Deployment

- **Production:** GitHub Actions deploys to GitHub Pages on push to `main` and daily at 06:00 UTC (`.github/workflows/deploy.yml`)
- **PR preview:** Builds on pull requests and uploads artifact (`.github/workflows/preview.yml`)

## Key conventions

- All HTML, CSS, and JS live inline in the Jinja2 template string (`TEMPLATE`) inside `build.py`
- Dark theme using CSS custom properties (see `:root` variables)
- Danish language for UI labels
- Tables support client-side sorting via `data-sort` attributes on `<td>` elements and `class="sortable"` on `<th>` elements
- Player names in tables are clickable links (`class="player-link"`) that toggle Elo chart display
- No external JS/CSS dependencies — everything is self-contained
