#!/usr/bin/env bash
set -euo pipefail

# Bootstrap Local Development Environment
# Sets up local development environment for podscrape2

PYTHON_BIN=${PYTHON:-python3}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Bootstrapping Podscrape2 Local Development Environment"
echo "Project root: $PROJECT_ROOT"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to print section headers
print_section() {
    echo ""
    echo "===================================================="
    echo "$1"
    echo "===================================================="
}

print_section "📋 Environment Check"

# Check Python version
echo "🐍 Checking Python..."
PYTHON_VERSION=$($PYTHON_BIN --version 2>&1)
echo "   Found: $PYTHON_VERSION"

if ! $PYTHON_BIN -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)" 2>/dev/null; then
    echo "   ❌ Python 3.9+ required"
    exit 1
fi
echo "   ✅ Python version OK"

# Check if .env exists
echo ""
echo "🔧 Checking environment configuration..."
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "   ❌ .env file not found"
    echo "   → Copy .env.sample to .env and configure your API keys"
    echo "   → cp .env.sample .env"
    exit 1
fi
echo "   ✅ .env file found"

# Check critical environment variables
echo "   Checking critical environment variables..."
ENV_MISSING=false

check_env_var() {
    local var_name="$1"
    local description="$2"

    # Load from .env file
    if grep -q "^${var_name}=" "$PROJECT_ROOT/.env" 2>/dev/null; then
        local var_value=$(grep "^${var_name}=" "$PROJECT_ROOT/.env" | cut -d'=' -f2- | sed 's/^"//' | sed 's/"$//')
        if [ -n "$var_value" ] && [ "$var_value" != "your-key-here" ] && [ "$var_value" != "test-key" ]; then
            echo "     ✅ $var_name: configured"
        else
            echo "     ❌ $var_name: $description"
            ENV_MISSING=true
        fi
    else
        echo "     ❌ $var_name: $description"
        ENV_MISSING=true
    fi
}

check_env_var "OPENAI_API_KEY" "OpenAI API key required for content scoring"
check_env_var "ELEVENLABS_API_KEY" "ElevenLabs API key required for TTS"
check_env_var "GITHUB_TOKEN" "GitHub token required for publishing"
check_env_var "GITHUB_REPOSITORY" "GitHub repository in OWNER/REPO format"

if [ "$ENV_MISSING" = true ]; then
    echo ""
    echo "   ⚠️  Some environment variables are missing or have placeholder values"
    echo "   → Edit .env and add your real API keys"
    echo "   → You can continue setup, but some features won't work"
fi

print_section "📦 Python Dependencies"

# Check if virtual environment should be used
if [ -n "${VIRTUAL_ENV:-}" ]; then
    echo "🔵 Virtual environment detected: $VIRTUAL_ENV"
elif [ -d "$PROJECT_ROOT/.venv" ]; then
    echo "🔵 Found existing .venv directory"
    echo "   → Activate with: source .venv/bin/activate"
else
    echo "💡 Consider creating a virtual environment:"
    echo "   → python3 -m venv .venv"
    echo "   → source .venv/bin/activate"
fi

echo ""
echo "📥 Installing Python dependencies..."
cd "$PROJECT_ROOT"

# Install requirements
if [ -f "requirements.txt" ]; then
    $PYTHON_BIN -m pip install --upgrade pip >/dev/null 2>&1 || true
    echo "   Installing from requirements.txt..."
    $PYTHON_BIN -m pip install -r requirements.txt >/dev/null
    echo "   ✅ Dependencies installed"
else
    echo "   ❌ requirements.txt not found"
    exit 1
fi

print_section "🗄️  Database Setup"

echo "🔗 Testing database connectivity..."
if $PYTHON_BIN scripts/doctor.py >/dev/null 2>&1; then
    echo "   ✅ Database connectivity check passed"
else
    echo "   ⚠️  Database connectivity issues detected"
    echo "   → Run 'python3 scripts/doctor.py' for details"
    echo "   → You may need to set up Supabase database tables"
fi

print_section "🏗️  Data Directories"

echo "📁 Creating data directories..."
DIRS=(
    "data/database"
    "data/transcripts"
    "data/scripts"
    "data/completed-tts"
    "data/logs"
    "data/rss"
    "data/backups"
    "public"
)

for dir in "${DIRS[@]}"; do
    mkdir -p "$PROJECT_ROOT/$dir"
    echo "   ✅ $dir"
done

print_section "🔧 External Tools"

echo "🛠️  Checking external tools..."

# Check ffmpeg
if command_exists ffmpeg; then
    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -n1 | cut -d' ' -f3)
    echo "   ✅ ffmpeg: $FFMPEG_VERSION"
else
    echo "   ❌ ffmpeg: Not found"
    echo "      → Install with: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)"
fi

# Check GitHub CLI
if command_exists gh; then
    GH_VERSION=$(gh --version | head -n1 | cut -d' ' -f3)
    echo "   ✅ gh CLI: $GH_VERSION"

    # Check authentication
    if gh auth status >/dev/null 2>&1; then
        echo "      ✅ GitHub CLI authenticated"
    else
        echo "      ⚠️  GitHub CLI not authenticated"
        echo "      → Run: gh auth login"
    fi
else
    echo "   ❌ gh CLI: Not found"
    echo "      → Install with: brew install gh (macOS)"
    echo "      → Alternative: Use GITHUB_TOKEN in .env"
fi

# Check PostgreSQL client
if command_exists psql; then
    PSQL_VERSION=$(psql --version | cut -d' ' -f3)
    echo "   ✅ PostgreSQL client: $PSQL_VERSION"
elif command_exists pg_dump; then
    PG_VERSION=$(pg_dump --version | cut -d' ' -f3)
    echo "   ✅ PostgreSQL client: $PG_VERSION"
else
    echo "   ❌ PostgreSQL client: Not found"
    echo "      → Install with: brew install postgresql (macOS)"
    echo "      → Needed for database backups"
fi

print_section "🧪 Development Tools"

echo "🔍 Setting up development tools..."

# Create or update .gitignore if needed
GITIGNORE_ENTRIES=(
    "*.pyc"
    "__pycache__/"
    ".DS_Store"
    "data/logs/*.log"
    "data/completed-tts/current/*.mp3"
    "data/transcripts/*.txt"
    "data/backups/*.sql"
)

if [ -f "$PROJECT_ROOT/.gitignore" ]; then
    echo "   ✅ .gitignore exists"
else
    echo "   📝 Creating .gitignore..."
    for entry in "${GITIGNORE_ENTRIES[@]}"; do
        echo "$entry" >> "$PROJECT_ROOT/.gitignore"
    done
    echo "   ✅ .gitignore created"
fi

print_section "✅ Bootstrap Complete"

echo "🎉 Local development environment is ready!"
echo ""
echo "📋 Next steps:"
echo "   1. Ensure all API keys are configured in .env"
echo "   2. Set up Supabase database: python3 scripts/migrate_sqlite_to_pg.py"
echo "   3. Run environment check: python3 scripts/doctor.py"
echo "   4. Test pipeline: python3 run_full_pipeline.py --phase discovery"
echo "   5. Start Web UI: bash scripts/run_web_ui.sh"
echo ""
echo "📚 Development commands:"
echo "   • Full pipeline: python3 run_full_pipeline.py"
echo "   • Publishing only: python3 run_publishing_pipeline.py"
echo "   • Environment check: python3 scripts/doctor.py"
echo "   • Web UI: bash scripts/run_web_ui.sh"
echo ""
echo "🔗 Documentation:"
echo "   • See README.md for complete setup guide"
echo "   • See CLAUDE.md for development guidelines"
echo "   • See move-online.md for deployment plan"

if [ "$ENV_MISSING" = true ]; then
    echo ""
    echo "⚠️  Remember to configure missing API keys in .env before running pipelines!"
fi