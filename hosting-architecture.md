# Hosting Architecture - Web UI Migration to Vercel

## Overview

Migration plan to move the Flask-based admin/status UI from local-only usage to a hosted deployment on Vercel, integrated with Supabase database and GitHub Actions for automated pipeline execution.

## Current Architecture

### Local Flask Application
- **Location**: `web_ui/` directory
- **Framework**: Flask + TailwindCSS + Alpine.js
- **Database**: PostgreSQL via Supabase with connection pooling
- **Configuration**: Database-backed settings via `WebConfigManager`
- **Access**: Local-only (127.0.0.1:5001)

### Pipeline Execution
- **Method**: Local command-line execution via `run_full_pipeline_orchestrator.py`
- **Database**: Direct PostgreSQL connection to Supabase
- **Publishing**: GitHub Releases + RSS generation + Vercel static deployment

## Target Hosted Architecture

### Vercel Application Structure
- **Framework**: Next.js + TypeScript + TailwindCSS (migration from Flask)
- **Deployment**: Serverless functions on Vercel platform
- **Domain**: Custom DNS pointing to Vercel (e.g., `admin.podcast.paulrbrown.org`)
- **Authentication**: Basic auth or GitHub OAuth for admin access

### Database Integration
- **Primary**: Supabase PostgreSQL with built-in connection pooling
- **Connection**: Serverless-optimized connection via `@supabase/postgrest-js`
- **Scaling**: Automatic connection pooling handles serverless function lifecycle
- **Backup**: Professional daily backups with 7+ day retention

### GitHub Actions Integration
- **Workflow Dispatch**: Trigger pipeline phases via GitHub REST API
- **Authentication**: Personal Access Token (PAT) with workflow scope
- **Phases**: Individual workflow triggers for discovery, audio, scoring, digest, TTS, publishing
- **Status Monitoring**: GitHub API for run status, logs, and artifacts

### Log Visibility Strategy
- **GitHub Logs**: Primary source via GitHub API for workflow run logs
- **Live Streaming**: Server-Sent Events (SSE) for real-time log viewing
- **Retention**: GitHub-managed log retention (90 days for private repos)
- **Fallback**: Link to GitHub Actions UI for full log access

## Component Migration Plan

### 1. Database Layer (No Changes Required)
- **Current**: Supabase PostgreSQL with SQLAlchemy models
- **Hosted**: Same Supabase instance, same connection patterns
- **Connection Pooling**: Built-in Supabase pooling handles serverless efficiently

### 2. Web UI Framework Migration
- **From**: Flask + Jinja2 templates
- **To**: Next.js + TypeScript + React components
- **Styling**: Retain TailwindCSS + Alpine.js patterns
- **API**: Convert Flask routes to Next.js API routes

### 3. Configuration Management
- **Current**: `WebConfigManager` with typed settings
- **Hosted**: Same `WebConfigManager` pattern, serverless-compatible
- **Settings**: Retain database-backed configuration approach

### 4. Pipeline Execution
- **Current**: Local CLI execution
- **Hosted**: GitHub Actions workflow dispatch via API
- **Trigger**: Serverless function calls GitHub API to start workflows
- **Monitoring**: GitHub API polling for status updates

## Security Architecture

### Authentication & Authorization
- **Admin Access**: Password-based or GitHub OAuth
- **Environment Variables**: Vercel-managed secrets for API keys
- **Database**: Existing Supabase RLS policies and service role access
- **GitHub**: PAT with minimal required scopes (workflow dispatch, repo read)

### Secret Management
- **Vercel Environment Variables**:
  - `DATABASE_URL` - Supabase connection string
  - `SUPABASE_SERVICE_ROLE` - Service role key for admin operations
  - `GITHUB_TOKEN` - PAT for workflow dispatch
  - `WEBUI_SECRET` - Simple auth secret for admin access
  - `OPENAI_API_KEY`, `ELEVENLABS_API_KEY` - API credentials

### Network Security
- **HTTPS**: Automatic via Vercel
- **CORS**: Configured for Supabase and GitHub API calls
- **Rate Limiting**: Implement for workflow dispatch endpoints

## Performance Considerations

### Serverless Optimization
- **Cold Starts**: Minimize by keeping functions lightweight
- **Connection Pooling**: Leverage Supabase built-in pooling
- **Caching**: Static asset caching via Vercel CDN
- **API Responses**: Cache GitHub API responses where appropriate

### Scalability
- **Concurrent Users**: Designed for 1-5 admin users
- **Database Connections**: Supabase pooling handles serverless load
- **GitHub API Limits**: Implement rate limiting and retry logic

## Deployment Strategy

### Phase 1: Parallel Development
- Develop Next.js app in `web_ui_hosted/` directory
- Test with same Supabase database
- Verify GitHub Actions integration

### Phase 2: Feature Parity
- Port all existing Flask functionality
- Implement workflow dispatch integration
- Add authentication layer

### Phase 3: DNS Migration
- Deploy to production Vercel instance
- Update DNS to point to Vercel
- Maintain Flask version as fallback

### Phase 4: Cleanup
- Archive Flask application
- Update documentation
- Monitor performance

## Operational Considerations

### Monitoring & Observability
- **Application**: Vercel analytics and logs
- **Database**: Supabase monitoring dashboard
- **Pipeline**: GitHub Actions workflow status
- **RSS Feed**: Monitor canonical URL availability

### Backup & Recovery
- **Database**: Automated Supabase backups
- **Configuration**: Version-controlled via Git
- **Secrets**: Documented backup of Vercel environment variables
- **Pipeline**: Reproducible via GitHub repository

### Maintenance
- **Updates**: Automated dependency updates via Dependabot
- **Security**: Regular security scanning
- **Performance**: Monitor and optimize based on usage patterns

## Success Metrics

### Functionality
- All existing Flask features accessible via Vercel deployment
- Successful workflow dispatch and monitoring
- RSS feed generation and publishing pipeline intact

### Performance
- Page load times < 2 seconds
- Workflow dispatch response < 5 seconds
- Database queries < 500ms average

### Reliability
- 99.9% uptime for admin interface
- Successful pipeline execution rate > 95%
- Zero data loss during migration

## Risk Mitigation

### Technical Risks
- **Database Connection**: Test connection pooling under serverless load
- **GitHub API Limits**: Implement proper rate limiting and error handling
- **Secret Management**: Secure migration of environment variables

### Operational Risks
- **DNS Migration**: Plan rollback strategy
- **Pipeline Disruption**: Maintain parallel execution capability
- **Data Loss**: Comprehensive backup before migration

### Mitigation Strategies
- Staged deployment with rollback capability
- Comprehensive testing in staging environment
- Parallel operation during transition period
- Documentation of all configuration and secrets