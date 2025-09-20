# Podcast Digest Admin - Hosted UI

Next.js-based admin interface for the RSS podcast digest system, designed for deployment on Vercel.

## Architecture

- **Framework**: Next.js 14 with App Router
- **Styling**: TailwindCSS
- **Database**: Supabase PostgreSQL with connection pooling
- **Deployment**: Vercel serverless functions
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

### Required for Vercel Deployment

- `DATABASE_URL` - PostgreSQL connection string
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_ROLE` - Service role key for admin operations
- `GITHUB_TOKEN` - GitHub PAT for workflow dispatch
- `WEBUI_SECRET` - Password for admin access

### Optional

- `OPENAI_API_KEY` - For pipeline dispatch
- `ELEVENLABS_API_KEY` - For pipeline dispatch

## Deployment

### Vercel Setup

1. **Connect repository** to Vercel
2. **Configure environment variables** in Vercel dashboard
3. **Deploy** - automatic deployment on git push

### DNS Configuration

Point your domain to Vercel:
```
podcast.paulrbrown.org → Vercel deployment
```

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

### Hosted Next.js UI
- Production admin interface
- Serverless-optimized
- GitHub Actions integration
- Supabase connection pooling

Both UIs share the same Supabase database and configuration system.