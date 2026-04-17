# Plan: Watch Themes + Post-Dedup Cleanup

## Context

Podcast dedup system has converged on a good place: semantic dedup via `claude -p` on
transcripts (pre-gen) and scripts (post-gen), with a 14-digest / 200k-char prior-content
window and dynamic evergreen-topic detection (v3.36, shipped 2026-04-16). Episode 611
(2026-04-17) is the first episode under the new dedup and is meaningfully better than
prior episodes.

As a side-effect of dedup's evolution, `story_arcs` are no longer consumed by script
generation (removed in commit 3ecc6e4). Arcs now serve only:

1. **ainewsletter** (external project on et01) — reads `story_arcs` every Friday to
   pick 3 stories for a weekly AI newsletter. Runs healthy, zero breakage from recent
   podcast changes.
2. **Auto "hot" promotion** — `is_hot`, `hot_briefing`, `retain_until`,
   `saturation_score` columns + `hot_briefing_generator.py`. Investigation shows
   **nothing currently consumes these values** (dedup doesn't use them, newsletter
   filters by event/source counts not `is_hot`, script gen no longer sees arc
   context). Appears to be vestigial.
3. **Retention scaffolding** — `cleanup_old_story_arcs()` uses `is_hot` + `retain_until`
   to preserve arcs from deletion.

Paul has identified 4 **curated personal interest themes** (paraphrased):
- AI impact on public company stock prices (quarterly-report disclosures)
- AI impact on politics (harm to anti-AI candidates)
- User hatred of Microsoft Copilot
- Claude Code as the defacto agentic coding product

These are **cross-cutting themes**, not single arcs. They won't be caught reliably by
the arc extractor's narrow clustering. Paul wants a **personal weekly digest**
highlighting matching transcript excerpts. We've named this concept **Watch Themes**.

Harold 2.0 (`harold.paulrbrown.org/briefs`) will host a 4th tab alongside Daily Brief /
Weekly Digest / Archive. Harold owns that codebase (Express.js + SQLite); the podcast
project owns generation (Supabase + Python + `claude -p`).

## Architecture

**Clean split**: podcast generates, Harold displays.

```
[Podcast Supabase]                    [Harold SQLite]
  watch_themes table     ──────┐
  (edited via podcast UI)       │      watch_digests table
                                │      (receives from POST)
[et01 cron, Sunday 7am PT]      │
  run_watch_digest.py:          │
    - read themes                │       [Harold Briefs page]
    - pull 7d AI&Tech            │         Daily | Weekly |
      transcripts                ▼         Archive | **Watch Themes**
    - claude -p per theme   ─────► email → brownpr0@gmail.com
    - assemble HTML          ─────► POST → harold/api/internal/watch-digest
```

Scope: **AI & Technology topic only** (Social Movements on hold).

## Task Sequence

Paul approved: fix ep 611 glitch → build watch themes → cleanup.

### Task 7 (first): Diagnose ep 611 closing-repeated-twice

- Pull the ep 611 generated script from DB or GitHub Release
- Pull the ep 611 TTS audio
- Determine whether duplication exists in the script (pre-TTS) or is a TTS artifact
  (post-TTS chunk concat or retry overlap)
- Fix root cause. Candidates: `src/audio/dialogue_chunker.py` boundary handling,
  `src/generation/dedup_pass.py` preserving intro/outro, TTS retry-join logic in
  `src/audio/audio_generator.py`.
- Gate: must land before next nightly cron (21:00 PT) to prevent recurrence.

### Tasks 1–5: Watch Themes build

**1. Alembic migration** — new `watch_themes` table on Supabase:
```sql
CREATE TABLE watch_themes (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE watch_themes ENABLE ROW LEVEL SECURITY;
CREATE POLICY service_all ON watch_themes FOR ALL TO service_role USING (true);
```
Plus SQLAlchemy model update.

**2. Settings UI** — new "Watch Themes" section in `web_ui_hosted/app/settings/page.tsx`:
list, add, edit, delete, toggle active. Mirror existing settings patterns. Seed with
Paul's 4 themes.

**3. Digest generator** — `scripts/run_watch_digest.py`:
- Load active watch themes
- Query transcripts from episodes with `topic='AI and Technology'`, status ∈ {digested,
  scored}, published in last 7 days
- For each theme: `claude -p` with system prompt = "you are scanning podcast
  transcripts for excerpts matching this theme" + theme description + concatenated
  transcripts. Return JSON of `{episode_title, episode_date, excerpt, relevance}`.
- Assemble HTML: one doc, 4 sections, each with theme name + matched excerpts linked
  to source episodes.
- Email via Graph API (reuse `ai-coder@vital-enterprises.com` credentials from
  `/Users/paulbrown/Desktop/coding-projects/.env` — but cron runs on et01, so
  credentials must also be on et01; confirm or copy).
- POST to `harold.paulrbrown.org/api/internal/watch-digest` with
  `X-Internal-Secret: $WATCH_DIGEST_SECRET` header, body `{date, html, markdown}`.

**4. et01 cron** — add to `crontab -l`:
```
0 7 * * 0 /srv/projects/podcast-pipeline/scripts/run_watch_digest.sh >> /home/pbrown/logs/watch-digest.log 2>&1
```
Wrapped by `run_pipeline_with_alerts.sh` pattern for failure alerts.

**5. Harold handoff prompt** — deliver drafted prompt to Harold. Prompt covers:
- Add 4th tab `Watch Themes` to `/briefs` (HTML + app.js + style inherit)
- Create `watch_digests(id, date UNIQUE, html, markdown, created_at)` via `src/db.ts`
- `GET /api/briefs/watch-themes` → latest row
- Extend `GET /api/briefs/archive?type=watch-themes` for archive listing
- New `POST /api/internal/watch-digest` with shared-secret auth (bypass session
  middleware for this one route)
- Add `WATCH_DIGEST_SECRET` to `.env` — same value on podcast side
- No content generation in Harold; purely a receiver + display

### Tasks 6 + 8: Cleanup (REVISED — two-stage after Codex review)

Codex caught that `is_hot` / `hot_briefing` / `saturation_score` are NOT vestigial —
`script_generator.py:641-794` actively reads them to build WELL-COVERED STORIES +
HOT STORY BRIEFINGS prompt sections. But dedup's evergreen detection (v3.36) now
functionally covers the WELL-COVERED work. So cleanup becomes two-stage:

**Stage 1 (Task 6a) — stop reads, keep columns**:
- In `script_generator.py`: remove WELL-COVERED STORIES section, HOT STORY BRIEFINGS
  section, hot-arc merging, and hot-arc grounding bypass.
- Keep columns, keep writes (hot_briefing_generator.py, auto-promotion), keep UI.
- Reversible by `git revert` of one commit.
- Monitor 7 days.

**Stage 2 (Task 6b) — drop columns, delete code (only after Stage 1 validates)**:
- Alembic migration dropping `is_hot`, `hot_briefing`, `retain_until`, `saturation_score`.
- Delete `hot_briefing_generator.py`, auto-promotion logic, UI hot toggles.
- Simplify `cleanup_old_story_arcs()` to pure age-based.

Tracking doc: `docs/hot-topic-deprecation-tracking.md` — review criteria, rollback
steps, files-to-change list for Stage 2 are documented there.

**Task 8 — Duplicate arc extraction**: unchanged from earlier plan.

**8. Duplicate arc extraction** — investigate:
- Determine whether ainewsletter's cron actually runs its own arc extractor or whether
  it only reads arcs written by the podcast project
- If it runs its own: are there duplicate/conflicting arcs in `story_arcs`? Query the
  table, group by `arc_name`, look for near-duplicates within short windows
- Recommend: podcast project owns arc extraction (it runs daily, sees more content);
  newsletter becomes pure consumer
- If duplicates exist: one-time merge pass via existing merge-arcs skill

## Risks & Unknowns

1. **Email from et01**: the ai-coder Graph API credentials live in the Mac's
   `.env`. et01 may not have them. Will confirm at runtime and copy if needed.
2. **Cron env vars**: need `WATCH_DIGEST_SECRET`, `ANTHROPIC_API_KEY` for claude -p,
   Supabase credentials, Graph API creds in et01 env.
3. **Theme match quality**: `claude -p` against a week's transcripts (likely 200k–500k
   chars total) may require careful chunking. If it exceeds context, fall back to
   per-episode scan + per-theme aggregation.
4. **Harold handoff timing**: we give Paul the prompt; Harold executes asynchronously.
   Podcast-side digest generator should gracefully handle "Harold endpoint returns 404"
   (log, continue, still send email).
5. **Ep 611 glitch root cause unknown** — if it's a TTS-side transient and not
   reproducible, worst case: add a defensive check in the script generator or dedup
   pass that rejects duplicate-outro patterns.
6. **is_hot demotion** — decided moot; we're deleting the feature, not fixing it.

## Success criteria

- Ep 611 glitch root cause identified; fix committed with regression test or guard
- Watch themes table + UI live; Paul can edit his 4 themes via the web
- First watch digest email lands in brownpr0@gmail.com next Sunday
- Harold tab displays that digest after Harold's prompt is executed
- Vestigial hot-topic code fully removed; no downstream breakage in ainewsletter
- Arc extraction has single source of truth
- Version bumped, commits atomic, zero build warnings
