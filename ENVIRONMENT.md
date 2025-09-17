# Environment Configuration Guide

**CRITICAL**: This system implements the **FAIL FAST** principle. If ANY required environment variable is missing or misconfigured, the system will:
1. Stop immediately with a clear error message
2. Exit with a non-zero status code
3. Show RED status in the Web UI system health
4. **Never attempt to run with incomplete configuration**

## Quick Setup

```bash
# 1. Copy the example environment file
cp .env.example .env

# 2. Edit .env with your actual API keys and configuration
vim .env

# 3. Source the environment
source .env

# 4. Validate your configuration
python3 scripts/doctor.py
```

## Required Environment Variables

### API Keys & Authentication

#### OpenAI Configuration
```bash
OPENAI_API_KEY="sk-..."
```
- **Purpose**: GPT-5-mini for content scoring, GPT-5 for script generation
- **Usage**: Content scoring against topics, digest script creation
- **Validation**: Must start with 'sk-' and be valid API key
- **Cost Impact**: Moderate (scoring ~$0.01-0.05 per episode, scripts ~$0.10-0.50 per digest)

#### ElevenLabs Configuration
```bash
ELEVENLABS_API_KEY="..."
```
- **Purpose**: Text-to-speech audio generation for podcast digests
- **Usage**: Converting generated scripts to MP3 audio files
- **Validation**: Must be valid ElevenLabs API key
- **Cost Impact**: High (TTS ~$0.30-1.00 per digest depending on length)

#### GitHub Configuration
```bash
GITHUB_TOKEN="ghp_..."
GITHUB_REPOSITORY="owner/repo"
```
- **Purpose**: Publishing MP3 files via GitHub Releases, managing RSS feed
- **Usage**: Daily release creation, asset uploads, repository management
- **Validation**:
  - Token must start with 'ghp_' or 'github_pat_'
  - Repository must be in 'owner/repo' format
  - Token must have repo permissions for target repository
- **Cost Impact**: Free (GitHub Releases are free)

### Database Configuration

#### Production Database (Supabase)
```bash
DATABASE_URL="postgresql://user:password@host:port/database"
```
- **Purpose**: PostgreSQL database for episodes, feeds, digests, settings
- **Usage**: All data persistence, Web UI configuration
- **Validation**: Must be valid PostgreSQL connection string
- **Format**: `postgresql://[user[:password]@][host][:port][/database][?param=value]`

#### Legacy Database (SQLite - Development Only)
```bash
DATABASE_URL="sqlite:///data/database/digest.db"
```
- **Purpose**: Local development and testing
- **Usage**: Development environment only
- **Validation**: Must be valid SQLite path
- **Note**: Not recommended for production use

### Optional Configuration

#### Development Environment Marker
```bash
ENV="development"
```
- **Purpose**: Enable development-specific features and logging
- **Usage**: Conditional development features, verbose logging
- **Default**: "production" if not set

#### Web UI Port Configuration
```bash
PORT="5001"
```
- **Purpose**: Custom port for Web UI
- **Usage**: Override default port 5001 for Web UI
- **Default**: 5001 if not set

## External Tool Dependencies

### Required System Tools

#### FFmpeg
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Validation
ffmpeg -version
```
- **Purpose**: Audio processing, chunking, format conversion
- **Usage**: Convert audio to ASR-compatible format, chunk large files
- **Critical**: Pipeline fails without FFmpeg

#### GitHub CLI
```bash
# macOS
brew install gh

# Ubuntu/Debian
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo gpg --dearmor -o /usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh

# Authentication
gh auth login

# Validation
gh --version
```
- **Purpose**: GitHub repository operations, release management
- **Usage**: Create releases, upload assets, manage repository
- **Critical**: Publishing phase fails without GitHub CLI

#### PostgreSQL Client Tools (Critical for Production)
```bash
# macOS (recommended: lightweight client-only)
brew install libpq
echo 'export PATH="/opt/homebrew/opt/libpq/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# macOS (alternative: full PostgreSQL)
brew install postgresql

# Ubuntu/Debian
sudo apt-get install postgresql-client

# RHEL/CentOS
sudo yum install postgresql

# Validation
pg_dump --version
```
- **Purpose**: Database backup and maintenance operations - **CRITICAL FOR PRODUCTION**
- **Usage**: Automated backups, database maintenance, disaster recovery
- **Auto-Discovery**: Scripts automatically find pg_dump in common installation paths
- **Status**: Required for data protection - production systems must have working backups

## Configuration Validation

### Environment Doctor Script
```bash
# Validate complete environment configuration
python3 scripts/doctor.py
```

**Expected Output** (23/23 checks should pass):
```
✅ Python Environment: python3 available and working
✅ FFmpeg: Available and working (-version flag)
✅ GitHub CLI: Available and authenticated
✅ OpenAI API: Valid API key and accessible
✅ ElevenLabs API: Valid API key and accessible
✅ Database: Connection successful (PostgreSQL/Supabase)
✅ PostgreSQL Tools: pg_dump available for database backups
✅ Required Python packages: All dependencies satisfied
```

**Note**: If pg_dump shows a warning (⚠️), it was found in a non-standard location. The system will work but you may want to add it to your PATH for consistency.

### Test Environment Validation
```bash
# Tests validate environment before running
python3 -m pytest tests/ -v
```

**Environment Validation Behavior**:
- Tests check all required environment variables before execution
- Missing variables cause immediate test failure with clear error messages
- Database automatically configured for SQLite in-memory testing
- Real API keys required for integration tests

## Environment File Template

Create `.env` with this template:

```bash
# =============================================================================
# RSS Podcast Digest System - Environment Configuration
# =============================================================================

# API Keys & Authentication
OPENAI_API_KEY=sk-your-openai-api-key-here
ELEVENLABS_API_KEY=your-elevenlabs-api-key-here

# GitHub Configuration
GITHUB_TOKEN=ghp_your-github-token-here
GITHUB_REPOSITORY=your-username/your-repo-name

# Database Configuration
DATABASE_URL=postgresql://user:password@host:port/database

# Optional Development Configuration
ENV=development
PORT=5001

# =============================================================================
# Security Notes:
# - Never commit .env file to version control
# - Rotate API keys regularly
# - Use environment-specific keys (dev/staging/prod)
# - Monitor API usage and costs
# =============================================================================
```

## Troubleshooting

### Common Issues

#### "OpenAI API key not found"
```bash
# Check if variable is set
echo $OPENAI_API_KEY

# Verify format
python3 -c "import os; key=os.environ.get('OPENAI_API_KEY'); print('Valid' if key and key.startswith('sk-') else 'Invalid')"
```

#### "Database connection failed"
```bash
# Test database connection
python3 -c "from src.config.env import require_database_url; require_database_url()"
```

#### "GitHub authentication failed"
```bash
# Check GitHub CLI authentication
gh auth status

# Re-authenticate if needed
gh auth login
```

#### "FFmpeg not found"
```bash
# Check FFmpeg installation
which ffmpeg
ffmpeg -version

# Install if missing (macOS)
brew install ffmpeg
```

#### "pg_dump not found"
```bash
# Check PostgreSQL installation
which pg_dump
pg_dump --version

# Install if missing
# macOS (lightweight - recommended)
brew install libpq
export PATH="/opt/homebrew/opt/libpq/bin:$PATH"

# Ubuntu/Debian
sudo apt-get install postgresql-client

# RHEL/CentOS
sudo yum install postgresql

# Test backup functionality
python3 scripts/db_backup.py --help
```

### Environment Validation Process

The system validates environment configuration in this order:

1. **Script Startup**: Each script validates its required environment variables
2. **Doctor Script**: Comprehensive validation of all tools and APIs
3. **Test Startup**: Tests validate environment before running any test cases
4. **Web UI Health**: Dashboard shows real-time environment status

### Security Best Practices

#### API Key Management
- Use separate API keys for development, staging, and production
- Rotate keys regularly (quarterly recommended)
- Monitor API usage and costs
- Never commit keys to version control
- Use key management services for production

#### Database Security
- Use strong passwords for database connections
- Enable SSL/TLS for database connections
- Restrict database access by IP if possible
- Regular backups with encryption

#### GitHub Security
- Use fine-grained personal access tokens
- Limit token permissions to required repositories
- Enable two-factor authentication
- Monitor repository access logs

## Cost Monitoring

### API Usage Estimates

**Daily Operation** (5 episodes, 2 digests):
- OpenAI: $0.15-0.75 (scoring + script generation)
- ElevenLabs: $0.60-2.00 (TTS generation)
- **Total**: ~$0.75-2.75 per day

**Monthly Estimates**:
- OpenAI: $4.50-22.50
- ElevenLabs: $18-60
- **Total**: ~$22.50-82.50 per month

### Cost Optimization
- Adjust score thresholds to reduce OpenAI calls
- Optimize script length to reduce TTS costs
- Use topic-based filtering to reduce processing volume
- Monitor usage via API dashboards

## Production Deployment

### Environment Checklist
- [ ] All API keys configured and validated
- [ ] Database URL points to production database
- [ ] GitHub repository configured for production
- [ ] External tools installed and working
- [ ] Environment doctor passes 22/23 checks
- [ ] Test suite passes with real environment
- [ ] Web UI health dashboard shows all green
- [ ] Cost monitoring alerts configured
- [ ] Backup strategy implemented
- [ ] Security review completed