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

## Troubleshooting

- **Deploy job says "FLY_API_TOKEN secret is not set"** — step 3 is missing; the tests still ran.
- **First page load takes a few seconds** — the machine and the database both sleep when idle and wake on the first request. That's what keeps it cheap.
- **Changing the password** — update `ADMIN_PASSWORD` in GitHub secrets and re-run the workflow.
- Ask Claude Code: *"the deploy failed, look at the latest Web app workflow run and fix it"*.

## Troubleshooting: login fails

Watch the app's logs while you try to log in:

```bash
fly logs -a padelstats-kleist
```

(or Fly dashboard → your app → **Logs & Errors**). Each failed login logs a reason, never the password itself:

- `ADMIN_PASSWORD is not set on the server`: the GitHub secret is missing or the deploy that syncs it hasn't run. Check with `fly secrets list -a padelstats-kleist`.
- `wrong letter case`: the phone capitalised the first letter.
- `wrong password (N chars submitted, M expected)`: a different password than the `ADMIN_PASSWORD` GitHub secret. Different lengths usually mean a typo or a stale secret; re-set the secret and re-run the **Web app** workflow.

Whitespace around the password (a phone's trailing space, a trailing newline in the secret) is ignored.
