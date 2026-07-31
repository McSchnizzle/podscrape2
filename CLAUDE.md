# CLAUDE.md

Automated RSS podcast digest system. This file is what a session needs to work here
safely; reference material lives in `docs/` and in the code.

**This project lives ONLY at `/srv/projects/podcast/` on et01.** There is no Mac
checkout and no rsync deploy. SSH to et01, edit in place, commit, push to
`origin/main`. The macOS setup section this file used to carry (Homebrew
installs, the GNU-prefixed timeout command) contradicted that and has been
removed; if you find similar guidance elsewhere, it is stale.

## Pipeline

```
RSS Feeds -> Episode Discovery -> Audio Download/Chunking -> Transcription (Whisper)
  -> Scoring -> Script Generation -> TTS -> Publishing (GitHub + dynamic RSS) -> Retention
```

Six phases: Discovery, Audio, Digest, TTS, Publishing, Retention.

```bash
python3 run_full_pipeline_orchestrator.py              # full run
python3 run_full_pipeline_orchestrator.py --phase audio # stop after a phase
python3 scripts/run_discovery.py   # or run_audio / run_digest / run_tts /
                                   # run_publishing / run_retention
```

Production: 9 PM PT daily via user crontab (`0 21 * * *`) wrapping
`scripts/run_pipeline_with_alerts.sh` through `~/patrol/cron-wrapper.sh`.

**Timeout is a live concern.** The cron wrapper allows 7200s. Runtime is trending
up and was last measured at 6247s (~86% of the cap). If runs start hitting the
ceiling, raise it to 10800s; if the baseline exceeds ~2h consistently,
investigate rather than raise again.

## Version: check the file, do not trust prose

Current version lives in `web_ui_hosted/app/version.ts` and **nowhere else**.
Read it; do not rely on any number written into documentation, including this
sentence.

```bash
grep VERSION web_ui_hosted/app/version.ts
```

Every commit increments it by 0.01 and names it in the commit message
(`feat: add feature (vX.YZ)`). This file used to hardcode a version string and
a worked increment example, both of which drifted about 1.5 major versions
behind the real value before anyone noticed. That is why the number is not
written here.

## Before every commit

Build errors and warnings both block a commit. `.husky/pre-commit` enforces it.

```bash
cd web_ui_hosted && npm run build
npx tsc --noEmit          # must be zero errors AND zero warnings
```

Three build-time traps that recur:

- **Module-level Supabase clients.** Never `const client = createClient()` at top
  level. Use a lazy getter or construct inside the function.
- **API routes reading env vars** need `export const dynamic = 'force-dynamic'`
  or they get prerendered.
- **Set iteration**: use `Array.from(new Set(...))`, not `[...new Set(...)]`, for
  the configured ES target.

## Traps that cost real time

### FFmpeg subprocess calls MUST pass stdin=subprocess.DEVNULL

FFmpeg enables interactive mode by default ("Press [q] to stop"). Without a TTY
-- cron, background, SSH -- it waits forever on stdin that never arrives, pins a
core at 100%, and never completes.

```python
subprocess.run(cmd, stdin=subprocess.DEVNULL,      # CRITICAL
               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
```

Affects every ffmpeg/ffprobe call in `src/podcast/audio_processor.py`. The
`-nostdin` flag also works but is less reliable.

### Environment config fails fast, deliberately

A missing or malformed required variable must stop the run immediately with a
non-zero exit and show RED in the Web UI health panel. No fallbacks, no silent
degradation. Required: `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `GITHUB_TOKEN`,
`GITHUB_REPOSITORY`, and `DATABASE_URL` (or Supabase config).
`scripts/doctor.py` validates all of them.

### The publishing repo MUST stay public

Podcatchers fetch GitHub release assets unauthenticated; a private repo returns
404 to every subscriber. `scripts/doctor.py` checks visibility.

### Python

Requires 3.13+ and the venv provides it. Always `python3`, never `python`.
Activate the venv before any ad-hoc database query, or imports resolve against
the wrong interpreter.

## Data and configuration are database-first

There are no filesystem fallbacks. Topics, topic instructions (`instructions_md`),
feeds, and web settings all live in PostgreSQL (Supabase); the RSS feed is
generated on demand by an API route, not written to disk.

Single database, two access stacks against the SAME Supabase instance:

| Stack | Language | Use | Entry point |
|---|---|---|---|
| SQLAlchemy ORM | Python | pipeline, scripts, migrations | `src/database/models.py` |
| Supabase JS | TypeScript | Web UI API routes | `web_ui_hosted/utils/supabase.ts` |

`supabase_schema.sql` is the authoritative schema contract; both stacks must
match it. Schema changes go through Alembic (`python3 -m alembic upgrade head`).

RLS is enabled on every public table. Backend and migrations use the service
role and bypass it; the Web UI uses `SUPABASE_SERVICE_ROLE`. **New tables must
enable RLS in the same migration** -- see `docs/database-rls.md` for the policy
block to copy.

Ad-hoc queries:

```bash
source .venv/bin/activate && python3 -c "
from src.database.models import get_database_manager
from src.database.sqlalchemy_models import Episode
session = get_database_manager().get_session()   # NOT .Session()
print(session.query(Episode).filter(Episode.status=='scored').count())
session.close()"
```

### Episode status machine

`pending -> processing -> transcribed -> scored -> digested`, with
`not_relevant` and `failed` as the other terminal states. `processing` is
transient and auto-resets if stuck over 10 minutes. Canonical list:
`src/database/episode_status.py`.

## Script generation

Two modes per topic, set by `script_mode` in the `topics` table:

- **dialogue** -- SPEAKER_1/SPEAKER_2 with audio tags, needs `voice_1_id` and
  `voice_2_id`, uses the ElevenLabs Text-to-Dialogue API with ~3k-char chunking
  at speaker boundaries.
- **narrative** -- single voice, `voice_1_id` only, standard TTS with text
  normalization.

Anti-AI writing rules (the banned-phrase list that shapes script voice) live in
`.claude/commands/generate-digest.md` and are enforced again by the cleanup and
structural-variety passes in `src/generation/script_generator.py`. Note the list
is currently duplicated across both files and `src/generation/dedup_pass.py`; if
you add a rule, add it to all of them or it will only be half-enforced.

Format details, tag vocabulary, and worked examples: `docs/script-formats.md`.

## Testing uses real data, never mocks

Real RSS feeds expose CDN behaviour, network faults, and malformed audio that
mocks hide. The established feeds are listed in `docs/test-feeds.md`.

## Models

Scoring and generation use the GPT-5 family (`gpt-5-mini` for scoring, `gpt-5`
for generation, with some `gpt-5.1`/`gpt-5.2` call sites). Confirm against the
code rather than this line:

```bash
grep -rhoE "gpt-[0-9.]+(-mini)?" src/ --include=*.py | sort | uniq -c | sort -rn
```

## Layout

```
src/config/       web settings, environment
src/database/     SQLAlchemy models (+ archived legacy SQLite)
src/podcast/      RSS parsing, audio processing, Whisper transcription
src/generation/   script generation, dedup, anti-AI passes
src/audio/        TTS, metadata, audio management
src/publishing/   GitHub uploads, database updates for the RSS API
src/utils/        logging, error handling
web_ui_hosted/    Next.js UI at podcast.paulrbrown.org
```

Serving: `podcast-web.service` (systemd **system** unit, port 3050) plus
`podcast-heartbeat.timer` every 5 minutes. Ingress via the existing
`cloudflared-tunnel.service` (`linus-et01`); hostname mapping in
`~/.cloudflared/config.yml`. Check with `systemctl is-active podcast-web.service`
-- it is a system unit, so `systemctl --user` will report it missing.

## Timezone

The user is in Pacific Time and et01 runs `America/Los_Angeles`. Convert UTC
timestamps in logs to PT when reporting.
