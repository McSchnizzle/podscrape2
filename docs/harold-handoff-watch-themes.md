# Harold handoff: add Watch Themes tab to /briefs

**To**: Harold (harold2.0 maintainer)
**From**: podcast project (Paul / Claude)
**Date**: 2026-04-17

Paste this entire file to Harold as a single task. He owns the harold2.0
codebase; we own the podcast-pipeline project that generates and POSTs the
digest content.

---

## What we need

Add a **4th tab labeled "Watch Themes"** to the existing `/briefs` page on
`harold.paulrbrown.org`, alongside Daily Brief / Weekly Digest / Archive.
The tab displays a personal weekly digest of AI-and-Technology podcast
content filtered to topics I care about (stock-price AI impact, political
AI impact, Copilot complaints, Claude Code adoption).

The podcast project generates the content and POSTs it to Harold weekly
(Sunday morning). Harold just stores and displays it. **No content
generation belongs in Harold.**

## Architecture

```
[podcast et01 cron, Sunday 7am PT]
   run_watch_digest.py scans week's transcripts,
   renders HTML, sends email, then:

POST https://harold.paulrbrown.org/api/internal/watch-digest
  Headers: X-Internal-Secret: <shared secret>
  Body: { "date": "YYYY-MM-DD", "html": "...", "markdown": "..." }

[harold2.0]
   stores in watch_digests table,
   serves via /api/briefs/watch-themes + /api/briefs/archive?type=watch-themes,
   rendered in the new tab.
```

## Concrete changes

### 1. Database — add `watch_digests` table

In `src/db.ts` (same pattern as `brief_archive`):

```sql
CREATE TABLE IF NOT EXISTS watch_digests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL UNIQUE,
  html TEXT NOT NULL,
  markdown TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Add helpers: `upsertWatchDigest(date, html, markdown)`, `getLatestWatchDigest()`,
`listWatchDigests(limit, offset)`.

### 2. Ingestion endpoint — `POST /api/internal/watch-digest`

In `src/web/routes/briefs.ts` or a new `src/web/routes/internal.ts`:

- **Auth**: shared secret, NOT session auth.
  Expect header `X-Internal-Secret`; compare to env var
  `WATCH_DIGEST_SECRET` (add to `.env` — generate 32-byte hex).
  Return 401 if missing/wrong. **Do NOT run this route through
  `authMiddleware`** — it's a machine-to-machine call.
- **Body validation**: `{ date: "YYYY-MM-DD", html: string, markdown?: string }`.
  Reject malformed dates.
- **Behavior**: upsert by `date` (overwrite if same date re-posts). Return
  `{ ok: true, id, updated: boolean }`.
- **Constant-time secret compare** using `crypto.timingSafeEqual`.

### 3. Display endpoints

- `GET /api/briefs/watch-themes` — latest row. Same response envelope as
  `GET /api/briefs/daily`. Session-auth required (inherits existing
  `authMiddleware`).
- Extend `GET /api/briefs/archive?type=watch-themes` — list watch_digests
  rows with the same pagination pattern used by daily/weekly archive
  (group by month, preview snippet, total/limit/offset).
- `GET /api/briefs/archive/:date?type=watch-themes` — fetch one historical
  watch digest by date.

### 4. Frontend — 4th tab

- In `public/index.html` (around the existing `.brief-tab` block, lines ~131–180):
  add `<button class="brief-tab" data-brief="watch-themes">Watch Themes</button>`.
- In `public/app.js` `loadBrief()` (around line 708): add case for
  `'watch-themes'`. Fetches from `/api/briefs/watch-themes`, renders HTML
  into the `.brief-content` div. Inherits existing styling — no CSS changes
  needed.
- Archive view: extend type filter dropdown to include "Watch Themes" as
  a selectable type. Existing archive code should just work with the new
  `type=watch-themes` parameter.

### 5. Environment

Add to Harold's `.env`:

```
WATCH_DIGEST_SECRET=<32-byte hex, same value on podcast side>
```

Paul will share the secret out-of-band once you're ready to deploy.

## Behaviour specifics

- **Idempotency**: podcast side will re-POST on manual re-runs. Upsert on
  `date` keeps one row per Sunday. No dedup needed on Harold's end beyond
  the UNIQUE constraint.
- **First few weeks have no data**: until first POST succeeds, `/api/briefs/
  watch-themes` should return a graceful empty state (not 500). Frontend
  should render "No watch digest yet — first one arrives Sunday" if API
  returns 404 or empty.
- **The HTML sent is self-contained**: it includes a small inline `<style>`
  block. It's safe to render inside your brief-content container as-is.
  No script tags, no external resources.
- **Security**: HTML is from the podcast generator (server-side, not user
  input), but still render it server-side into the response body rather
  than letting the client fetch arbitrary strings. Same trust model as
  daily brief markdown → HTML.

## Not in scope

- Generation of the digest content (podcast side owns this)
- Theme management UI (podcast web UI handles theme CRUD)
- Email delivery (podcast side sends email directly via Graph API)

## Validation

Paul will POST a test digest from his laptop after you deploy:

```bash
curl -X POST https://harold.paulrbrown.org/api/internal/watch-digest \
  -H "X-Internal-Secret: $WATCH_DIGEST_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"date":"2026-04-19","html":"<p>Hello from watch themes</p>","markdown":"Hello"}'
```

Then load the /briefs page, click Watch Themes, confirm content renders.

## Reference

Podcast-side generator: `scripts/run_watch_digest.py` in the `podcast-pipeline`
repo. DB migration: `alembic/versions/j6e7f8g9h0i1_add_watch_themes_and_favorites.py`.
Design doc: `docs/audio-incidents.md` + `docs/hot-topic-deprecation-tracking.md`
(for context, not required reading).

Questions → ping Paul.
