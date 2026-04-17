# Watch Themes deployment runbook

Two deployable pieces: (a) podcast-side generator + cron on et01, (b) Harold
receives the handoff prompt in `docs/harold-handoff-watch-themes.md`.

## Prerequisites

- Alembic migration `j6e7f8g9h0i1_add_watch_themes_and_favorites.py` applied
  on production Supabase (already applied from local `alembic upgrade head`
  since we share the DB — confirm).
- Watch themes seeded in production (already done — the 4 themes Paul listed
  are in the `watch_themes` table).

## Secrets required on et01

Add to `/srv/projects/podcast-pipeline/.env` (if not already present):

```bash
# Microsoft Graph (ai-coder sender for personal watch digest emails)
EMAIL_AZURE_TENANT_ID=<from laptop .env>
EMAIL_AZURE_CLIENT_ID=<from laptop .env>
EMAIL_AZURE_CLIENT_SECRET=<from laptop .env>

# Harold ingestion (generate new 32-byte hex; same value on Harold's .env)
WATCH_DIGEST_SECRET=<openssl rand -hex 32>

# Harold base URL (default in the script is correct, but overridable)
HAROLD_BASE_URL=https://harold.paulrbrown.org
```

Check current state:

```bash
ssh et01 'grep -E "EMAIL_AZURE|WATCH_DIGEST" /srv/projects/podcast-pipeline/.env || echo MISSING'
```

If Graph creds are missing, copy from laptop `.env`:

```bash
# from laptop
grep "^EMAIL_AZURE_" /Users/paulbrown/Desktop/coding-projects/.env | \
  ssh et01 'cat >> /srv/projects/podcast-pipeline/.env'
```

Generate and set the shared secret:

```bash
SECRET=$(openssl rand -hex 32)
ssh et01 "echo 'WATCH_DIGEST_SECRET=$SECRET' >> /srv/projects/podcast-pipeline/.env"
echo "Harold needs this same value: $SECRET"
```

## Deploy code to et01

Use existing rsync script (`scripts/deploy_to_et01.sh`) — it will pick up the
new files automatically. Verify after deploy:

```bash
ssh et01 'ls -la /srv/projects/podcast-pipeline/scripts/run_watch_digest.*'
# expect both run_watch_digest.py and run_watch_digest.sh
ssh et01 'test -x /srv/projects/podcast-pipeline/scripts/run_watch_digest.sh && echo OK'
```

## First manual test (dry-run)

```bash
ssh et01 'cd /srv/projects/podcast-pipeline && \
  source .venv/bin/activate && \
  python3 scripts/run_watch_digest.py --dry-run'
# writes HTML to /srv/projects/podcast-pipeline/data/watch-digest-dryrun-<date>.html
```

Inspect the HTML. If it looks sensible, run for real (will send email + try
Harold POST):

```bash
ssh et01 'cd /srv/projects/podcast-pipeline && \
  source .venv/bin/activate && \
  python3 scripts/run_watch_digest.py'
```

Check `brownpr0@gmail.com` inbox. Harold POST may 404 until Harold deploys
his side — that's fine, email still lands, audit row records
`harold_delivered=false`.

## Cron entry (Sunday 7am PT)

Add to `crontab -l` on et01, following the existing podcast pipeline pattern:

```
# WATCH THEMES PERSONAL DIGEST — Sundays 7 AM Pacific
0 7 * * 0 /home/pbrown/patrol/cron-wrapper.sh watch-digest --timeout 1800 -- bash -c '/srv/projects/podcast-pipeline/scripts/run_watch_digest.sh >> /home/pbrown/logs/watch-digest-cron.log 2>&1'
```

To install:

```bash
ssh et01 'crontab -l > /tmp/ct.bak && \
  (crontab -l; echo "# WATCH THEMES PERSONAL DIGEST — Sundays 7 AM Pacific"; \
   echo "0 7 * * 0 /home/pbrown/patrol/cron-wrapper.sh watch-digest --timeout 1800 -- bash -c '"'"'/srv/projects/podcast-pipeline/scripts/run_watch_digest.sh >> /home/pbrown/logs/watch-digest-cron.log 2>\&1'"'"'") | crontab -'
ssh et01 'crontab -l | grep watch-digest'
```

Backup of previous crontab is at `/tmp/ct.bak` on et01. Don't run the install
command without Paul's OK — it modifies shared server state.

## Rollback

Remove the cron line:

```bash
ssh et01 'crontab -l | grep -v watch-digest | crontab -'
```

The script itself is harmless if never invoked — no cleanup needed beyond
the crontab row.

## Monitoring

- Audit table: `SELECT * FROM watch_digest_runs ORDER BY run_date DESC LIMIT 5`
- Logs: `ssh et01 'tail -50 /home/pbrown/logs/watch-digest-cron.log'`
- Email delivered flag: per-run `email_delivered` column
