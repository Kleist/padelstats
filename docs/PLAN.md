# Padel Stats 2.0 — plan

## Goals

1. **Enter results from the phone** — open a website, log in once, type in a match in under 30 seconds.
2. **A proper database** instead of a Google Sheet, so data is validated, structured and backed up.
3. **Automatic deployment** — merging to `main` deploys; nothing is done by hand on a server.
4. **Developable from the phone via Claude Code** — describe a change in the Claude app, Claude opens a PR, CI proves it works, you merge from the phone, it deploys.
5. **Cheap** — a few dollars a month at most.

## Architecture

```
 Phone browser ──HTTPS──▶  Fly.io (FastAPI app, Docker, Frankfurt)  ──SQL──▶  Neon Postgres (Frankfurt)
                                    ▲
 Claude Code (phone) ──PR──▶ GitHub ──Actions: lint → tests (on real Postgres) → deploy──┘
```

| Piece | Choice | Why |
|---|---|---|
| Language | **Python (FastAPI + Jinja2)** | Reuses the existing stats code and its 47 tests; server-rendered HTML needs no JS build step. |
| Database | **Postgres on [Neon](https://neon.tech)** | Real managed Postgres with a free tier, point-in-time restore, and database *branches* (a copy of prod per PR — useful for previews later). |
| Schema changes | **Alembic migrations** | Every schema change is a reviewed file in git; applied automatically on deploy. CI fails if models and migrations drift. |
| Hosting | **[Fly.io](https://fly.io)** | Runs our Docker image, scales to zero when idle (pay only while running), deploys from GitHub Actions with a single token. No server to maintain. |
| CI/CD | **GitHub Actions** | Already used. Tests run against a real Postgres. Deploy runs migrations first, then smoke-tests the live URL for the exact commit. |
| Login | **Shared password → signed cookie (1 year)** | Only needed to *enter* results; stats are public. Replaced by per-player logins in Phase 4. |

### Expected cost

- Neon: free tier (0.5 GB — this app will use a few MB).
- Fly.io: pay-as-you-go, needs a credit card. One small machine (256 MB) that stops when idle: roughly **$0–2/month**.
- Total: **≈ $0–3/month.** No fixed subscription.

### Alternatives considered

- **Cloudflare Workers + D1** — cheaper (free) and very fast, but means rewriting the stats in TypeScript or using the still-maturing Python Workers. Good option if Fly ever disappoints.
- **Railway / Render** — similar to Fly with nicer dashboards, but managed Postgres there costs ~$5–7/month extra.
- **Supabase** — good, but free projects pause after a week of inactivity and Pro is $25/month.
- **Keep Google Sheets + a form** — cheapest, but not a proper database and no validation.

## Developing from the phone

1. In the Claude app (Claude Code), ask for a change: *"add a page showing head-to-head records"*.
2. Claude works on a branch, runs lint + tests (the SessionStart hook installs dependencies automatically), and opens a PR.
3. GitHub Actions runs the same checks against a real Postgres.
4. You look at the PR (and later a preview link) in the GitHub app and merge.
5. `main` deploys automatically; the workflow fails loudly if the live site isn't serving the new commit.

## Phases

### Phase 0 — Prototype (this PR) ✅ built, needs one-time setup

Proves the whole pipeline: phone → web app → database → automatic deploys.

- FastAPI app (`app/`): list of latest matches, login, mobile form to enter a match (date, inde/ude, 4 players with autocomplete, up to 6 sets).
- Postgres schema (`players`, `matches`, `match_sets`) via Alembic.
- `/healthz` and `/healthz/db` endpoints reporting the deployed commit.
- `.github/workflows/app.yml`: lint → tests on Postgres → migration check → deploy to Fly → smoke test.
- Existing GitHub Pages site is untouched and keeps running from the Google Sheet.

**Done when:** after the [setup](SETUP.md), you can open `https://padelstats-kleist.fly.dev` on your phone, enter a match, and see it in the list; and merging a trivial PR changes the version shown in the footer.

### Phase 1 — Move the data

- Import script: Google Sheet → database (idempotent, so it can be re-run until cut-over).
- Verification test: stats computed from the database equal stats computed from the Sheet.
- Nightly backup: GitHub Action runs `pg_dump` and stores it as an artifact (Neon's free restore window is short).

### Phase 2 — Stats in the app

- Move `parse/compute_*` from `build.py` into a shared module used by both the static build and the app.
- Render leaderboard, Elo (with chart), pairs and match history in the app, live from the database — same look as today.
- Keep the golden-file acceptance test.

### Phase 3 — Cut over

- Stop entering data in the Sheet; the app is the source of truth.
- `kleist.github.io/padelstats` redirects to the app (or keep it as a static mirror built from the database).
- Optional: own domain (e.g. `padel.example.dk`) — Fly certificates are free.

### Phase 4 — Nice to have

- Edit/delete a match (with an audit log of who changed what).
- **Per-player login** (decided): magic link by email instead of one shared password. Each match records who entered it. Stats stay public — login only gates entering/editing results.
- "Add to home screen" (PWA icon + manifest).
- **PR previews**: each PR gets its own Fly app + Neon branch with a copy of the data, link posted on the PR — so you can try changes on the phone before merging.

## Decisions

- **Stats are public** — no login needed to view anything. Login only gates entering (and later editing) results.
- **Player logins later** — shared password for now; per-player logins in Phase 4.

## Open questions

- Own domain or `*.fly.dev`?
