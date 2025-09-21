# Validation & Testing Checklist

This checklist covers the smoke tests required before shipping the hosted Supabase+Vercel deployment to production.

## 1. Database & Migration Verification
- [ ] Run `python3 -m alembic upgrade head` against Supabase (already executed) and confirm `topics`, `topic_instruction_versions`, `digest_episode_links`, `pipeline_runs` tables exist via `psql` or Supabase UI.
- [ ] Execute `python3 scripts/migrate_topics_to_supabase.py --dry-run` (sanity check) followed by `python3 scripts/migrate_topics_to_supabase.py` for the real import (completed once; rerun only if seeds change).
- [ ] Inspect Supabase tables to ensure:
  - `topics` rows match hosted UI (slugs, descriptions, active flags).
  - `topic_instruction_versions` contains initial version entries per topic.
  - `pipeline_runs` receives new rows when orchestrator/workflow executes.
  - `digest_episode_links` populates when digests are generated.

## 2. Pipeline Smoke Test (Avoiding TTS Costs)
- [ ] Set `DRY_RUN=true` and run `python3 run_full_pipeline_orchestrator.py --phase digest --verbose` locally to exercise discovery → digest without TTS.
- [ ] Verify a new `pipeline_runs` record appears with phase history in Supabase.
- [ ] Check `data/logs/` for orchestrator log and ensure no filesystem topics are referenced.
- [ ] Inspect Supabase `topics.last_generated_at` updates for topics that produced digests.

## 3. Publishing Path Validation
- [ ] Dispatch the publishing-only workflow from the hosted `/publishing` page (or `gh workflow run publishing-only.yml`).
- [ ] Confirm `pipeline_runs` captures the run and `/publishing` UI reflects the job under "Supabase Pipeline Runs".
- [ ] Ensure digests with existing MP3 assets mark `published_at` and `github_url` after workflow completion.

## 4. Hosted UI Regression (Manual)
Using the Vercel preview (or local `npm run dev`):
- [ ] `/dashboard` shows system health, Supabase stats, and recent pipeline activity.
- [ ] `/topics` loads Supabase-backed topics, allows edits (slug/name/voice) and persists changes.
- [ ] `/script-lab` loads instructions from Supabase, saves new versions, and reflects knob updates.
- [ ] `/episodes` lists recent episodes with feed titles and digest inclusion badges.
- [ ] `/publishing` displays recent digests and the GitHub dispatch form.
- [ ] `/maintenance` lists pipeline runs, GitHub workflow activity, and dispatches full pipeline.

## 5. Automation & Caching (Planned)
- [ ] Add Playwright smoke tests covering critical flows: login (if applicable), Topics CRUD, Script Lab save, Episodes filter, Publishing dispatch, Maintenance dashboard.
- [ ] Evaluate Next.js static/ISR caching: add `revalidateTag`/`revalidatePath` hooks in API routes once data flow stabilizes.
- [ ] Document cache invalidation strategy in `OPERATIONS.md` after implementation.

## 6. Pre-Production Checklist
- [ ] Verify `.env.example` reflects Supabase-first variables.
- [ ] Update README/PRD (done) if any new workflow toggles or environment variables are introduced.
- [ ] Create/Update PR with migration notes, validation steps, and screenshots of Publishing/Maintenance pages.

> Track completion state by checking boxes and linking to workflow runs/logs in the PR description.
