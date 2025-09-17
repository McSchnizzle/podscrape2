"""
Pytest fixtures for database testing and integration tests.
Provides isolated test environments with real database connections.
"""

from __future__ import annotations

import importlib
import logging
import os
import sys
import tempfile
from datetime import datetime, date, timedelta
from typing import Generator

import pytest

# FAIL FAST: Test Environment Validation
def pytest_configure(config):
    """
    Validate test environment BEFORE running any tests.
    Implements FAIL FAST principle - exit immediately if configuration is incomplete.
    """
    # Critical environment variables for full test functionality
    required_env_vars = {
        'DATABASE_URL': 'Database connection (set automatically to sqlite:///:memory: for tests)',
        'OPENAI_API_KEY': 'OpenAI API access for content scoring and script generation tests',
        'ELEVENLABS_API_KEY': 'ElevenLabs TTS API for audio generation tests',
        'GITHUB_TOKEN': 'GitHub repository access for publishing tests',
        'GITHUB_REPOSITORY': 'Target repository in format owner/repo'
    }

    missing_vars = []
    for var_name, description in required_env_vars.items():
        if var_name not in os.environ or not os.environ[var_name].strip():
            # DATABASE_URL is auto-set for tests, others must be provided
            if var_name != 'DATABASE_URL':
                missing_vars.append(f"  ❌ {var_name}: {description}")

    if missing_vars:
        error_msg = "\n" + "="*80 + "\n"
        error_msg += "🚨 CRITICAL: Test Environment Validation Failed (FAIL FAST)\n"
        error_msg += "="*80 + "\n"
        error_msg += "Required environment variables are missing or empty:\n\n"
        error_msg += "\n".join(missing_vars)
        error_msg += "\n\n"
        error_msg += "FAIL FAST Principle: Tests cannot run with incomplete configuration.\n"
        error_msg += "Fix environment configuration before running tests.\n"
        error_msg += "\n"
        error_msg += "Quick setup:\n"
        error_msg += "  1. Copy .env.example to .env\n"
        error_msg += "  2. Fill in all required API keys and configuration\n"
        error_msg += "  3. Source the environment: source .env\n"
        error_msg += "  4. Validate with: python3 scripts/doctor.py\n"
        error_msg += "="*80 + "\n"

        # Print to stderr and exit immediately
        import sys
        sys.stderr.write(error_msg)
        sys.stderr.flush()
        sys.exit(2)  # Exit code 2 indicates critical failure

    # Success: Environment validation passed
    print("✅ Test Environment Validation: All required environment variables present")

# Ensure CLI tests can run even when the legacy runner module is absent
if 'run_full_pipeline' not in sys.modules:
    try:
        importlib.import_module('run_full_pipeline')
    except ModuleNotFoundError:
        from tests.stubs import run_full_pipeline_stub

        sys.modules['run_full_pipeline'] = run_full_pipeline_stub

# Attempt to import SQLAlchemy. If unavailable (e.g., offline testing environments),
# database-dependent tests will be skipped gracefully.
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool

    SQLALCHEMY_AVAILABLE = True
except ModuleNotFoundError:
    SQLALCHEMY_AVAILABLE = False
    create_engine = text = Session = sessionmaker = StaticPool = None  # type: ignore

if SQLALCHEMY_AVAILABLE:
    from src.database.models import DatabaseManager, Digest, Episode, Feed
    from src.database.models import get_digest_repo, get_episode_repo, get_feed_repo
    from src.database.sqlalchemy_models import Base
else:
    DatabaseManager = Digest = Episode = Feed = None  # type: ignore
    Base = None
    get_digest_repo = get_episode_repo = get_feed_repo = None  # type: ignore

# Configure test environment
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'


@pytest.fixture(scope="session")
def test_database_engine():
    """Create an in-memory SQLite database for testing"""
    if not SQLALCHEMY_AVAILABLE:
        pytest.skip("SQLAlchemy not available in test environment")

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False  # Set to True for SQL debugging
    )

    # Create all tables
    Base.metadata.create_all(engine)

    return engine


@pytest.fixture(scope="function")
def test_db_session(test_database_engine) -> Generator[Session, None, None]:
    """Create a fresh database session for each test"""
    if not SQLALCHEMY_AVAILABLE:
        pytest.skip("SQLAlchemy not available in test environment")

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_database_engine)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def test_db_manager(test_database_engine):
    """Create a DatabaseManager instance for testing"""
    if not SQLALCHEMY_AVAILABLE:
        pytest.skip("SQLAlchemy not available in test environment")

    # Clear all tables before each test for isolation
    Base.metadata.drop_all(test_database_engine)
    Base.metadata.create_all(test_database_engine)

    db_manager = DatabaseManager()
    # Override the engine with our test engine
    db_manager.engine = test_database_engine
    db_manager.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_database_engine)
    return db_manager


@pytest.fixture(scope="function")
def episode_repo(test_db_manager):
    """Create an EpisodeRepository for testing"""
    if not SQLALCHEMY_AVAILABLE:
        pytest.skip("SQLAlchemy not available in test environment")
    return get_episode_repo(test_db_manager)


@pytest.fixture(scope="function")
def feed_repo(test_db_manager):
    """Create a FeedRepository for testing"""
    if not SQLALCHEMY_AVAILABLE:
        pytest.skip("SQLAlchemy not available in test environment")
    return get_feed_repo(test_db_manager)


@pytest.fixture(scope="function")
def digest_repo(test_db_manager):
    """Create a DigestRepository for testing"""
    if not SQLALCHEMY_AVAILABLE:
        pytest.skip("SQLAlchemy not available in test environment")
    return get_digest_repo(test_db_manager)


@pytest.fixture
def sample_feed():
    """Create a sample feed for testing"""
    if not SQLALCHEMY_AVAILABLE:
        pytest.skip("SQLAlchemy not available in test environment")
    return Feed(
        feed_url="https://example.com/feed.xml",
        title="Test Podcast",
        description="A test podcast for unit testing",
        active=True,
        consecutive_failures=0,
        total_episodes_processed=0,
        total_episodes_failed=0
    )


@pytest.fixture
def sample_episode():
    """Create a sample episode for testing"""
    if not SQLALCHEMY_AVAILABLE:
        pytest.skip("SQLAlchemy not available in test environment")
    return Episode(
        episode_guid="test-episode-123",
        feed_id=1,
        title="Test Episode",
        published_date=datetime.now() - timedelta(days=1),
        audio_url="https://example.com/audio.mp3",
        duration_seconds=1800,
        description="A test episode for unit testing",
        status='pending'
    )


@pytest.fixture
def sample_episode_with_scores(sample_episode):
    """Create a sample episode with AI scores"""
    sample_episode.scores = {
        "AI and Technology": 0.85,
        "Politics": 0.25,
        "Climate": 0.60
    }
    sample_episode.scored_at = datetime.now()
    sample_episode.status = 'scored'
    return sample_episode


@pytest.fixture
def sample_digest():
    """Create a sample digest for testing"""
    if not SQLALCHEMY_AVAILABLE:
        pytest.skip("SQLAlchemy not available in test environment")
    return Digest(
        topic="AI and Technology",
        digest_date=date.today(),
        episode_ids=[1, 2, 3],
        episode_count=3,
        average_score=0.75
    )


@pytest.fixture
def populated_database(test_db_manager, feed_repo, episode_repo, digest_repo):
    """Create a database populated with test data"""
    if not SQLALCHEMY_AVAILABLE:
        pytest.skip("SQLAlchemy not available in test environment")
    # Create test feed
    feed = Feed(
        feed_url="https://test.example.com/feed.xml",
        title="Test Podcast Feed",
        description="Test feed for integration testing",
        active=True
    )
    feed_id = feed_repo.create(feed)

    # Create test episodes
    episodes = []
    for i in range(5):
        episode = Episode(
            episode_guid=f"test-episode-{i}",
            feed_id=feed_id,
            title=f"Test Episode {i+1}",
            published_date=datetime.now() - timedelta(days=i),
            audio_url=f"https://test.example.com/audio{i}.mp3",
            duration_seconds=1800 + (i * 300),
            description=f"Test episode {i+1} description",
            status='pending' if i < 2 else 'scored',
            scores={"AI and Technology": 0.8 - (i * 0.1)} if i >= 2 else None,
            scored_at=datetime.now() if i >= 2 else None
        )
        episode_id = episode_repo.create(episode)
        episode.id = episode_id
        episodes.append(episode)

    # Create test digest
    digest = Digest(
        topic="AI and Technology",
        digest_date=date.today() - timedelta(days=1),
        episode_ids=[episodes[2].id, episodes[3].id],
        episode_count=2,
        average_score=0.75,
        script_path="/tmp/test_script.md",
        script_word_count=500
    )
    digest_id = digest_repo.create(digest)
    digest.id = digest_id

    return {
        'feed_id': feed_id,
        'episodes': episodes,
        'digest_id': digest_id
    }


@pytest.fixture
def temp_directory():
    """Create a temporary directory for test files"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def disable_logging():
    """Disable logging during tests to reduce noise"""
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing"""
    original_env = os.environ.copy()

    # Set test environment variables
    test_env = {
        'OPENAI_API_KEY': 'test-openai-key',
        'ELEVENLABS_API_KEY': 'test-elevenlabs-key',
        'GITHUB_TOKEN': 'test-github-token',
        'GITHUB_REPOSITORY': 'test/repo',
        'DATABASE_URL': 'sqlite:///:memory:',
        'ENV': 'test'
    }

    os.environ.update(test_env)

    yield test_env

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def real_database_test():
    """
    Fixture for tests that need the real Supabase database.
    Use sparingly and only for integration tests.
    """
    # Temporarily override to use real database
    original_url = os.environ.get('DATABASE_URL')
    if not original_url:
        pytest.skip("Real database tests require DATABASE_URL")

    # Use the real database manager
    db_manager = DatabaseManager()

    yield db_manager

    # Cleanup - this fixture should be used carefully
    # to avoid affecting production data


@pytest.fixture
def real_feed_data():
    """
    Provides real RSS feed data with optional caching for performance.
    Maintains real data testing philosophy while allowing performance optimization.
    """
    from tests.test_data_cache import test_cache

    def get_feed(feed_name: str = "bridge", use_cache: bool = True):
        """Get real RSS feed data, optionally cached."""
        return test_cache.get_feed_data(feed_name, use_cache)

    return get_feed


@pytest.fixture
def real_episode_data():
    """
    Provides real episode data from RSS feeds with optional caching.
    """
    from tests.test_data_cache import test_cache

    def get_episodes(feed_name: str = "bridge", count: int = 3, use_cache: bool = True):
        """Get real episode data from RSS feeds."""
        return test_cache.get_sample_episodes(feed_name, count, use_cache)

    return get_episodes


@pytest.fixture
def test_data_cache():
    """
    Direct access to test data cache for advanced test scenarios.
    """
    from tests.test_data_cache import test_cache
    return test_cache


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_cache():
    """
    Clean up test cache after test session.
    Ensures fresh state for next test run.
    """
    yield

    # Clean up cache directory if it exists
    from tests.test_data_cache import test_cache
    cache_dir = test_cache.cache_dir
    if cache_dir.exists():
        import shutil
        shutil.rmtree(cache_dir)
        print(f"🗑️  Cleaned up test cache directory: {cache_dir}")