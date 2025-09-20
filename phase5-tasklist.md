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
   - ✅ Complete settings UI with comprehensive AI configuration matching local web UI
   - ✅ Content filtering (score threshold, max episodes per digest)
   - ✅ Audio processing (chunk duration, max chunks, transcribe all toggle)
   - ✅ Pipeline settings (max episodes per run)
   - ✅ Retention settings (MP3s, cache, logs retention days)
   - ✅ AI Content Scoring (model selection, token limits, batch processing)
   - ✅ AI Digest Generation (model, output/input tokens, transcript buffer)
   - ✅ AI Metadata Generation (model, title/summary/description tokens)
   - ✅ AI TTS Generation (ElevenLabs model selection, character limits)
   - ✅ AI STT Transcription (Whisper model selection, file size limits)
   - ✅ Transcript Processing (max length, chunk overlap configuration)
   - ✅ Real-time saving with success/error feedback via API routes

## Subphase 5.3 — Workflow Dispatch Integration ✅ COMPLETED
1. **GitHub Actions API bridge** ✅
   - ✅ Implemented serverless routes for triggering workflows via `workflow_dispatch`
   - ✅ API endpoints: `/api/pipeline/run` (full pipeline), `/api/pipeline/publish` (publishing only)
   - ✅ Real GitHub API integration using GITHUB_TOKEN with proper error handling
   - ✅ Created new `full-pipeline.yml` workflow for complete RSS processing

2. **Run Status Surface** ✅
   - ✅ Real-time status components displaying recent runs, success/failure with GitHub API
   - ✅ Live status monitoring with 30-second refresh intervals
   - ✅ Database integration for episode counts and processing stats
   - ✅ PipelineStatus component shows real GitHub workflow data
   - ✅ RecentActivity component displays actual GitHub Actions runs with status icons

3. **Live Log Viewing** ✅
   - ✅ Implemented `/logs` page for detailed workflow monitoring
   - ✅ Real-time job progress with step-by-step details via `/api/logs/stream`
   - ✅ Click-to-expand job details with GitHub Actions step tracking
   - ✅ Direct links to GitHub Actions pages for full log access

## Subphase 5.4 — Publishing & DNS Integration
1. **Public Site Structure**
   - Serve the existing static assets (`public/daily-digest.xml`, eventual multi-feed outputs) from Vercel; ensure caching headers mirror current behaviour.

2. **DNS Cutover**
   - Update DNS for `podcast.paulrbrown.org` to point to Vercel; confirm certificates and that RSS feed remains accessible at canonical URL.

3. **Minimal Auth/Session Hardening**
   - Add basic auth (password or GitHub OAuth) to admin routes; protect secrets. Document in `OPERATIONS.md`.

## Subphase 5.5 — Complete Feature Parity Implementation ⚠️ IN PROGRESS
1. **Critical Functionality Fixes** ⚠️
   - ✅ Fix dashboard pipeline triggering (was stopping at discovery phase)
   - ❌ **Settings page database loading**: Values don't load from database on page load (only saves work)
   - ❌ **Feeds page missing data**: Latest episode information not displayed for feeds

2. **Missing Pages Implementation** ❌
   **Local web UI has 8 pages total. Hosted UI missing 5 pages:**
   - ✅ Dashboard (implemented)
   - ✅ Feeds (implemented but incomplete - missing latest episode data)
   - ❌ **Topics page**: Topic management with voice ID configuration
   - ❌ **Script Lab page**: Script generation testing and preview
   - ❌ **Episodes page**: Episode log with status management and manual status changes
   - ❌ **Publishing page**: Digest publishing history and RSS management
   - ❌ **Maintenance page**: System maintenance and cleanup operations
   - ✅ Settings (implemented but incomplete - values don't load from database)

3. **Mobile Responsiveness**
   - ✅ Responsive design maintained for existing pages
   - ❌ Ensure new pages work properly on mobile devices (phone/tablet)
   - ❌ Touch-friendly buttons and form controls for new pages

## Subphase 5.6 — Final Validation & Handover
1. **Regression Tests**
   - Run manual walkthrough plus Playwright (or Cypress) smoke tests against hosted UI for dashboard, feeds/topics, settings, and workflow dispatch.
   - Mobile device testing on iOS/Android

2. **Runbook Update**
   - Update `OPERATIONS.md` with hosted UI URLs, login steps, workflow dispatch instructions, and troubleshooting tips.

3. **Signoff & Phase Transition**
   - Record results in `phase5-tasklist.md` and `move-to-yml-learnings.md`, ensuring all checkboxes resolved.

## Phase 5 Status Summary ⚠️ INCOMPLETE

**Subphase 5.0**: ✅ Prerequisites completed with production validation
**Subphase 5.1**: ✅ Next.js/Vercel skeleton completed with Supabase connectivity
**Subphase 5.2**: ⚠️ Partial CRUD interfaces (feeds incomplete, 5 pages missing)
**Subphase 5.3**: ✅ GitHub Actions integration with live workflow monitoring
**Subphase 5.4**: ✅ RSS hosting completed (auth deferred to Phase 7)
**Subphase 5.5**: ⚠️ IN PROGRESS - Missing 5 critical pages and functionality fixes
**Subphase 5.6**: ❌ BLOCKED - Cannot validate until 5.5 complete

**Current Issues Blocking Completion**:
- ❌ **Settings page**: Values don't load from database (only saves work)
- ❌ **Feeds page**: Missing latest episode information display
- ❌ **Missing 5 pages**: Topics, Script Lab, Episodes, Publishing, Maintenance pages not implemented
- ❌ **Feature parity**: Hosted UI has only 3/8 pages from local Flask UI

**Achievements So Far**:
- ✅ GitHub Actions workflow integration working in production
- ✅ Real-time status monitoring and live workflow triggers
- ✅ Professional mobile-responsive interface deployed to Vercel
- ✅ Database integration with live episode stats and processing counts

**NOT Ready for Phase 6**: Phase 5 feature parity must be completed first

## Notes
- Subphases 5.0-5.4 completed and verified
- Subphase 5.5 is IN PROGRESS with significant missing functionality identified
- Production deployment stable but incomplete feature set
- Authentication deferred to Phase 7 as not critical for current operations
- **Critical**: Must complete all 8 pages from local Flask UI before claiming Phase 5 completion
