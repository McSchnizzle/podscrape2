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

## Subphase 5.1 — Hosted UI Skeleton on Vercel
1. **Create Next.js/Vercel Project Stub**
   - Scaffold a new UI project (likely Next.js + TypeScript + Tailwind) living under `web_ui_hosted/` (or reuse existing structure if convertible).
   - Deploy “Hello World” page to Vercel, confirm DNS alias or preview URL.

2. **Environment & Secrets**
   - Configure Vercel env vars: `DATABASE_URL`, `SUPABASE_SERVICE_ROLE` or connection string, `WEBUI_SECRET`, GitHub token for workflow dispatch.
   - Document secret mapping in `OPERATIONS.md`.

3. **Supabase Connectivity**
   - Implement serverless Supabase client with connection pooling (e.g., `@supabase/postgrest-js` or `pg` via Neon/Vercel pooled connection).
   - Create minimal API route that queries `feeds` to prove DB access from Vercel.

## Subphase 5.2 — Port Existing UI Screens
1. **Dashboard Status**
   - Recreate dashboard page showing pipeline status (latest run info, queue state) using data from Supabase tables and GitHub API (for workflow runs).
   - Determine strategy for live updates (polling Actions API, webhooks, or streaming logs).

2. **Feeds & Topics CRUD**
   - Reimplement feeds/topics CRUD forms using the Supabase client. Ensure validation and error handling mirror the Flask version.

3. **Settings Page**
   - Port the settings UI, including new token limit fields; ensure values persist via Supabase and reflect back in forms.

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
