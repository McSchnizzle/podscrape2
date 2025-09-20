# Phase 5 Task List — Web UI Hosting & DNS Migration

Goal: move the Flask-based admin/status UI from local-only usage to a hosted deployment on Vercel, wired into Supabase and GitHub Actions. We’ll work through incremental subphases so each milestone is easy to verify.

## Subphase 5.0 — Wrap Up Phase 4 Prerequisites
1. **Tune Digest & Episode Limits**
   - Review current settings in `web_settings` and lower `ai_digest_generation` token caps (input/output) to reasonable values for Vercel/Actions execution.
   - Confirm orchestrator with `--phase digest` finishes in a production (non-dry-run) mode using current configs.
   - Update `OPERATIONS.md` with the tested settings.

2. **Production Run Through Digest**
   - Execute `python run_full_pipeline_orchestrator.py --phase digest` (or equivalent workflow) to validate discovery → audio → scoring → digest end-to-end with real writes.
   - Capture logs/artifacts and note runtime/perf observations for inclusion on the hosted UI.

3. **Document Hosting Architecture Decisions** ✅
   - Draft a short architecture note covering Vercel app structure, Supabase connection pooling, GitHub dispatch approach, auth mechanism, and log visibility plan.
   - Store the doc alongside `move-to-yml-learnings.md` for easy reference.
   - **Completed**: See `hosting-architecture.md` for comprehensive migration plan and technical specifications.

## Subphase 5.1 — Hosted UI Skeleton on Vercel ✅ COMPLETED
1. **Create Next.js/Vercel Project Stub** ✅
   - ✅ Scaffolded Next.js 14 + TypeScript + TailwindCSS project under `web_ui_hosted/`
   - ✅ App Router structure with dashboard, feeds, settings, API routes
   - ✅ Component library with SystemHealth, PipelineStatus, RecentActivity
   - ✅ Ready for Vercel deployment with proper configuration

2. **Environment & Secrets** ✅
   - ✅ Created `.env.example` with all required variables
   - ✅ Documented in README.md and ready for Vercel configuration
   - ✅ Environment variables: DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE, GITHUB_TOKEN, WEBUI_SECRET

3. **Supabase Connectivity** ✅
   - ✅ Implemented serverless Supabase client with service role authentication
   - ✅ DatabaseClient class with connection pooling support
   - ✅ API routes: `/api/health` for system health checks
   - ✅ TypeScript interfaces for database entities (Feed, Episode, Digest, WebSetting)

## Subphase 5.2 — Port Existing UI Screens ✅ COMPLETED
1. **Dashboard Status** ✅
   - ✅ Recreated dashboard page with SystemHealth component showing database connectivity
   - ✅ Real-time status checks with Supabase health monitoring
   - ✅ Ready for GitHub API integration for workflow status

2. **Feeds CRUD** ✅
   - ✅ Complete feeds management interface at `/feeds` with full CRUD operations
   - ✅ Extended DatabaseClient with createFeed, updateFeed, deleteFeed, toggleFeedActive methods
   - ✅ API routes: GET/POST `/api/feeds`, PUT/DELETE `/api/feeds/[id]`
   - ✅ Modal-based add/edit forms with URL validation and error handling
   - ✅ Health status indicators (healthy/warning/error) and active/inactive toggles
   - ✅ Real-time feedback and loading states matching design system

3. **Settings Page** ✅
   - ✅ Complete settings UI with all configuration categories
   - ✅ Content filtering (score threshold, max episodes per digest)
   - ✅ Audio processing (chunk duration, max chunks, transcribe all toggle)
   - ✅ Pipeline settings (max episodes per run)
   - ✅ Retention settings (MP3s, cache, logs retention days)
   - ✅ Real-time saving with success/error feedback via API routes

## Subphase 5.3 — Workflow Dispatch Integration
1. **GitHub Actions API bridge**
   - Implement serverless route that triggers workflows (`phase-discovery`, `phase-audio`, etc.) via `workflow_dispatch`, using PAT with workflow scope.
   - Add minimal auth guard (`WEBUI_SECRET` or simple password form) before allowing dispatch.

2. **Run Status Surface**
   - Build status components that display recent runs, success/failure, and links to artifacts. Consider using GitHub REST API or GraphQL.

3. **Live Log Viewing**
   - Decide on best-effort log streaming (polling with `gh api /logs`, or linking to GitHub run pages). Implement at least a basic log link per run.

## Subphase 5.4 — Publishing & DNS Integration
1. **Public Site Structure**
   - Serve the existing static assets (`public/daily-digest.xml`, eventual multi-feed outputs) from Vercel; ensure caching headers mirror current behaviour.

2. **DNS Cutover**
   - Update DNS for `podcast.paulrbrown.org` to point to Vercel; confirm certificates and that RSS feed remains accessible at canonical URL.

3. **Minimal Auth/Session Hardening**
   - Add basic auth (password or GitHub OAuth) to admin routes; protect secrets. Document in `OPERATIONS.md`.

## Subphase 5.5 — Final Validation & Handover
1. **Regression Tests**
   - Run manual walkthrough plus Playwright (or Cypress) smoke tests against hosted UI for dashboard, feeds/topics, settings, and workflow dispatch.

2. **Runbook Update**
   - Update `OPERATIONS.md` with hosted UI URLs, login steps, workflow dispatch instructions, and troubleshooting tips.

3. **Signoff & Phase Transition**
   - Record results in `phase5-tasklist.md` and `move-to-yml-learnings.md`, ensuring all checkboxes resolved.

## Notes
- Treat each subphase as independent verification; only progress when the prior subphase is signed off.
- Keep a separate `hosted-ui` branch until Vercel deployment is stable.
