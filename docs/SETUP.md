# One-time setup (≈15 minutes, can be done from a phone browser)

You need three accounts: Neon (database), Fly.io (hosting) and GitHub (already have it).
After this, every merge to `main` deploys automatically.

## 1. Database — Neon

1. Go to <https://console.neon.tech> and sign up (e.g. "Continue with GitHub").
2. Create a project:
   - Name: `padelstats`
   - Region: **AWS Europe Central 1 (Frankfurt)**
3. On the project dashboard, click **Connect**. Turn **Connection pooling off**, and copy the connection string.
   It looks like `postgresql://neondb_owner:...@ep-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`.

## 2. Hosting — Fly.io

1. Go to <https://fly.io/app/sign-up> and sign up. Add a credit card under **Billing** (required; expected cost is about $0–2/month).
2. Create an access token: **Account → Access Tokens → Create token**, type **Org deploy token**, org `personal`.
   (Org token, not app token — the workflow creates the app the first time.)
3. Copy the token (starts with `FlyV1 ...`).

## 3. GitHub secrets

Open <https://github.com/Kleist/padelstats/settings/secrets/actions> (on the phone, use "Desktop site" in the browser if needed) and add three **repository secrets**:

| Name | Value |
|---|---|
| `FLY_API_TOKEN` | the Fly token from step 2 |
| `DATABASE_URL` | the Neon connection string from step 1 |
| `ADMIN_PASSWORD` | a password you and your padel friends will use to enter results |

Optional, under the **Variables** tab: `FLY_APP` if the name `padelstats-kleist` is taken (the deploy will fail with "name has already been taken").

## 4. Deploy

Merge the prototype PR — or go to **Actions → Web app → Run workflow** on `main`.
The **deploy** job creates the Fly app, stores the secrets on it, runs database migrations, deploys, and checks that the live site reports the new commit.

Open <https://padelstats-kleist.fly.dev>, tap **+ Indtast kamp**, log in, enter a match. 🎾
Tip: in the browser menu, choose **Add to Home Screen**.

## 5. Staging (optional): try a PR before merging

Every pull request can deploy to a separate staging app, <https://padelstats-kleist-staging.fly.dev>, which uses its own database so production data is never touched.

1. In Neon, open the project → **Branches → Create branch**. Name it `staging` and create it from `main`. You get a copy of the production data, and it doesn't cost extra while idle.
2. Click **Connect** on the `staging` branch, turn **Connection pooling off**, and copy the connection string.
3. Add it as a repository secret named `STAGING_DATABASE_URL`.

Each push to a PR then runs tests and deploys the PR to staging. Migrations run against the staging database only. The PR page shows a **View deployment** button, and the workflow posts the staging link as a PR comment (one comment per PR, updated on every staging deploy). Staging uses the same `ADMIN_PASSWORD` and has its own login cookie. There is only one staging app, so the most recently pushed PR is the one running there.

Every staging deploy wipes the staging database and restores the latest nightly production backup into it (see 7. Backups). Each PR therefore starts from fresh production data, its migrations are tested against real data, and every PR checks that the backups can actually be restored: if the restore fails, the staging deploy fails. Anything entered on staging is lost on the next deploy. Until a backup exists, the staging deploy fails: run **Actions → Database backup** once, then re-run the failed job.

Without `STAGING_DATABASE_URL`, the staging deploy is skipped with a warning.

## 6. Import the matches from the Google Sheet

The app is now the source of truth and the Sheet is no longer used; this section is kept for reference. Re-running the import overwrites matches imported from the Sheet with the Sheet's current rows (matches entered in the app are never touched).

Uses the `GOOGLE_SHEETS_API_KEY` and `SPREADSHEET_ID` secrets.

1. Go to **Actions → Import from Google Sheet → Run workflow** (branch `main`, target `production`).
2. Keep **Only show what would change** ticked the first time. The run summary lists new/updated rows, skipped rows with the reason (fix them in the Sheet), and whether the stats match.
3. Run it again with the box unticked to save. Re-run it any time until cut-over to pick up new Sheet rows.

Target `staging` imports into the staging database instead (needs `STAGING_DATABASE_URL`).

## 7. Backups

**Database backup** runs every night and stores a `pg_dump` of production as an artifact (kept 90 days): **Actions → Database backup → latest run → Artifacts**. Run it by hand once to check it works. Every staging deploy restores the latest backup, so a broken backup shows up as a failed staging deploy.
If the repository is public, any logged-in GitHub user can download these artifacts. They hold only player names and results, which are public anyway.

To restore a backup (e.g. into a new Neon branch), unzip the artifact and run:

```bash
pg_restore --no-owner --no-acl --clean --if-exists -d "<connection string>" padelstats-<date>.dump
```

## Troubleshooting

- **Deploy job says "FLY_API_TOKEN secret is not set"** — step 3 is missing; the tests still ran.
- **First page load takes a few seconds** — the machine and the database both sleep when idle and wake on the first request. That's what keeps it cheap.
- **Changing the password** — update `ADMIN_PASSWORD` in GitHub secrets and re-run the workflow.
- Ask Claude Code: *"the deploy failed, look at the latest Web app workflow run and fix it"*.

## Troubleshooting: login fails

Watch the app's logs while you try to log in:

```bash
fly logs -a padelstats-kleist          # or padelstats-kleist-staging
```

(or Fly dashboard → your app → **Logs & Errors**). Each failed login logs a reason, never the password itself:

- `ADMIN_PASSWORD is not set on the server`: the GitHub secret is missing or the deploy that syncs it hasn't run. Check with `fly secrets list -a padelstats-kleist`.
- `wrong letter case`: the phone capitalised the first letter.
- `wrong password (N chars submitted, M expected)`: a different password than the `ADMIN_PASSWORD` GitHub secret. Different lengths usually mean a typo or a stale secret; re-set the secret and re-run the **Web app** workflow.

Whitespace around the password (a phone's trailing space, a trailing newline in the secret) is ignored.
