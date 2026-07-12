# Podcast Digest Admin - Hosted UI

Next.js-based admin interface for the RSS podcast digest system.

> **Deployment note (v3.45+):** This app is **NOT deployed on Vercel.** It is
> self-hosted on the **et01** server as the `podcast-web.service` systemd unit
> listening on **port 3050**, fronted by the existing `cloudflared-tunnel.service`
> (`linus-et01` tunnel) which maps `podcast.paulrbrown.org` to `127.0.0.1:3050`.
> A `podcast-heartbeat.timer` pings `/api/heartbeat` every 5 minutes (this
> replaced the old Vercel cron). Any older references to Vercel serverless
> deployment are historical and no longer accurate.

## Architecture

- **Framework**: Next.js 14 with App Router
- **Styling**: TailwindCSS
- **Database**: local PostgreSQL (on et01), accessed via SQLAlchemy (Python
  pipeline) and the Supabase JS client (this app); see the repo `CLAUDE.md`
  "Database Architecture" section
- **Deployment**: self-hosted `podcast-web.service` (systemd) on et01, port 3050
- **Ingress**: `cloudflared-tunnel.service` (`linus-et01`) → `127.0.0.1:3050`
- **Authentication**: Basic auth via WEBUI_SECRET

## Local Development

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Set up environment**:
   ```bash
   cp .env.example .env.local
   # Edit .env.local with your credentials
   ```

3. **Run development server**:
   ```bash
   npm run dev
   ```

4. **Open browser**: http://localhost:3000

## Environment Variables

### Required

- `DATABASE_URL` - PostgreSQL connection string
- `SUPABASE_URL` - Supabase-compatible project URL (JS client)
- `SUPABASE_SERVICE_ROLE` - Service role key for admin operations
- `GITHUB_TOKEN` - GitHub PAT for publishing / workflow dispatch
- `WEBUI_SECRET` - Password for admin access

### Optional

- `OPENAI_API_KEY` - For pipeline dispatch
- `ELEVENLABS_API_KEY` - For pipeline dispatch

## Deployment (self-hosted on et01)

The app runs as a systemd service on the et01 server. There is **no** Vercel
project, no `git push`-triggered serverless deploy, and no Vercel dashboard for
environment variables.

Typical deploy / update flow on et01:

```bash
# On et01, in the repo checkout:
cd web_ui_hosted
npm ci
npm run build

# Restart the service to pick up the new build:
sudo systemctl restart podcast-web.service

# Health / status:
systemctl status podcast-web.service
curl -s http://127.0.0.1:3050/api/heartbeat
```

Environment variables are provided to the service via its systemd unit /
`.env` on et01 (not a Vercel dashboard).

### Ingress / DNS

`podcast.paulrbrown.org` is served through the existing Cloudflare tunnel
(`cloudflared-tunnel.service`, tunnel `linus-et01`); the hostname → port
mapping lives in `/home/pbrown/.cloudflared/config.yml` and points to
`127.0.0.1:3050`. DNS is a Cloudflare tunnel CNAME, not a Vercel target.

## Features

### Dashboard
- System health monitoring
- Pipeline status and controls
- Recent activity feed
- Quick actions

### Feeds Management
- Add/edit RSS feeds
- Health status monitoring
- Activate/deactivate feeds

### Settings
- AI model configuration
- Token limits
- Processing thresholds
- TTS settings

### Pipeline Control
- Manual workflow dispatch
- Real-time status monitoring
- Log viewing
- Error handling

## API Routes

- `GET /api/health` - System health check
- `GET /api/heartbeat` - Liveness ping (polled by `podcast-heartbeat.timer`)
- `POST /api/pipeline/run` - Trigger pipeline workflow
- `GET /api/feeds` - List RSS feeds
- `POST /api/feeds` - Create/update feed
- `GET /api/settings` - Get configuration
- `POST /api/settings` - Update configuration

## Development vs Production

### Local Flask UI
- Full-featured development interface
- Direct database access
- Local pipeline execution

### Hosted Next.js UI (this app)
- Production admin interface
- Self-hosted on et01 as `podcast-web.service` (port 3050)
- **Pipeline execution**: cron jobs on the et01 server (9 PM PT), migrated from
  GitHub Actions in v2.72 and fully consolidated to et01 in v3.45

Both UIs share the same PostgreSQL database and configuration system.
