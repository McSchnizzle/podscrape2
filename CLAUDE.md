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

Two modes per topic, set by **`use_dialogue_api`** (a boolean) in the `topics`
table. This file said `script_mode` for a long time; there is no such column.

- **dialogue** (`use_dialogue_api = true`) -- SPEAKER_1/SPEAKER_2 with audio
  tags, needs `voice_1_id` and `voice_2_id`, uses the ElevenLabs
  Text-to-Dialogue API with ~3k-char chunking at speaker boundaries.
- **narrative** -- single voice, `voice_1_id` only, standard TTS with text
  normalization.

Anti-AI writing rules (the banned-phrase list that shapes script voice) live in
`src/generation/anti_ai_rules.py`, the single source of truth. The markdown
skill file `.claude/commands/generate-digest.md` cannot import Python, so it
keeps a hand-maintained copy that `tests/test_anti_ai_rules_sync.py` guards.
`src/generation/dedup_pass.py` still carries its own inline copy and does not
import the shared list -- it is unwired from production, so this costs nothing
today, but revive it and you inherit the drift.

### The digest finalization path (v4.01)

`create_digest` ends at `finalize_script()`, and that is the only place
post-generation work belongs. It runs the structural variety pass exactly once
on the draft that actually ships, then the lead-repeat guard
(`src/generation/lead_repeat_guard.py`), which refuses to open a digest with a
story the last three digests opened with.

Three things about it are load-bearing and were each learned the hard way, so
do not "simplify" them without reading the tests first:

- It runs **after** the hard-floor check. The variety pass trims 1-2%, so
  running it earlier lets polish push a legitimate script under the floor and
  destroy the night's digest.
- The guard scores **word tokens with `autojunk=False`**, and takes the **max
  across several windows**. Character-wise scoring rates a verbatim repeat
  lower than two unrelated digests; a single wide window misses a repeat that
  ends after four turns.
- Every failure path returns the draft unchanged. The guard must never be the
  reason a digest fails to generate.

`tests/test_finalize_script.py` asserts the wiring and the ordering, because
v3.48 replaced this call with a comment and nobody noticed for three months.

Format details, tag vocabulary, and worked examples: `docs/script-formats.md`.
Incident history and the full remediation plan: `script-upgrade-plan.md`.

## Testing uses real data, never mocks

Real RSS feeds expose CDN behaviour, network faults, and malformed audio that
mocks hide. The established feeds are listed in `docs/test-feeds.md`.

## Models

**What the pipeline runs today**: the GPT-5 family -- `gpt-5-mini` for scoring
and topic extraction, `gpt-5` / `gpt-5.2` at the generation call sites. The
Claude path (`claude -p`, free under the Max subscription) drives the
structural-variety rewrite.

**Current frontier models, as of 2026-07-31** -- the pipeline is a generation
behind and migrating is a deliberate cost/quality decision, not a cleanup:

| Family | Models | Notes |
|---|---|---|
| OpenAI GPT-5.6 | `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna` | `gpt-5.6` aliases to sol. Sol = flagship, Terra = balanced, Luna = fastest/cheapest |
| Anthropic Claude 5 | `claude-opus-5`, `claude-sonnet-5` | plus `claude-haiku-4-5-20251001` |

Do not trust the table over the config. Models are set in the database
(`web_settings`, and `dialogue_model` per topic), so read those:

```bash
grep -rhoE "gpt-[0-9.]+[a-z-]*" src/ --include=*.py | sort | uniq -c | sort -rn
```

`gpt-4` still appears once in `src/generation/script_generator.py` inside the
`known_entities` list. That is a DETECTION keyword for transcripts that discuss
GPT-4, not a model selection. Leave it.

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

**Nothing is hosted on Vercel.** Verified 2026-07-31: responses from
podcast.paulrbrown.org carry no `x-vercel-*` headers, only cloudflare, and the
tunnel points at localhost:3050. The two `vercel.json` files were removed; the
`/daily-digest.xml` rewrite they contained is duplicated in
`web_ui_hosted/next.config.js`, which is what actually serves it.

## Timezone

The user is in Pacific Time and et01 runs `America/Los_Angeles`. Convert UTC
timestamps in logs to PT when reporting.
