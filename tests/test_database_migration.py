"""
Integration tests for database migration - transcript and script content storage.
Tests the new database-only storage functionality.
"""

import pytest

pytest.importorskip("sqlalchemy", reason="SQLAlchemy is required for database integration tests")

from datetime import datetime, date, UTC
from src.database.models import Episode, Digest, get_episode_repo, get_digest_repo


class TestTranscriptDatabaseStorage:
    """Test transcript storage in database"""

    def test_episode_transcript_storage(self, episode_repo, sample_episode):
        """Test storing and retrieving transcript content in database"""
        # Create episode
        episode_id = episode_repo.create(sample_episode)
        assert episode_id is not None

        # Test transcript content storage
        test_transcript = """# Test Transcript
This is a test transcript with some content.
Multiple lines of text to verify storage.
Special characters: áéíóú ñ"""

        episode_repo.update_transcript(
            sample_episode.episode_guid,
            None,  # No file path
            100,   # Word count
            test_transcript
        )

        # Retrieve and verify
        retrieved_episode = episode_repo.get_by_guid(sample_episode.episode_guid)
        assert retrieved_episode is not None
        assert retrieved_episode.transcript_content == test_transcript
        assert retrieved_episode.transcript_word_count == 100
        assert retrieved_episode.transcript_path is None  # No file path stored

    def test_episode_transcript_large_content(self, episode_repo, sample_episode):
        """Test storing large transcript content"""
        # Create episode
        episode_id = episode_repo.create(sample_episode)

        # Generate large transcript content
        large_transcript = "Test transcript content. " * 1000  # ~25KB

        episode_repo.update_transcript(
            sample_episode.episode_guid,
            None,
            len(large_transcript.split()),
            large_transcript
        )

        # Retrieve and verify
        retrieved_episode = episode_repo.get_by_guid(sample_episode.episode_guid)
        assert retrieved_episode.transcript_content == large_transcript
        assert len(retrieved_episode.transcript_content) > 20000


class TestScriptDatabaseStorage:
    """Test script storage in database"""

    def test_digest_script_storage(self, digest_repo, sample_digest):
        """Test storing and retrieving script content in database"""
        # Create digest
        digest_id = digest_repo.create(sample_digest)
        assert digest_id is not None

        # Test script content storage
        test_script = """# Test Script
## Topic: Technology

Today's digest covers exciting developments in tech.

### Key Points:
- AI advances continue
- New frameworks emerge
- Security improvements

This is a comprehensive script with markdown formatting."""

        digest_repo.update_script(
            digest_id,
            None,  # No file path
            150,   # Word count
            test_script
        )

        # Retrieve and verify
        retrieved_digest = digest_repo.get_by_id(digest_id)
        assert retrieved_digest is not None
        assert retrieved_digest.script_content == test_script
        assert retrieved_digest.script_word_count == 150
        assert retrieved_digest.script_path is None  # No file path stored

    def test_digest_script_update(self, digest_repo, sample_digest):
        """Test updating script content"""
        # Create digest
        digest_id = digest_repo.create(sample_digest)

        # Initial script
        initial_script = "Initial script content"
        digest_repo.update_script(digest_id, None, 10, initial_script)

        # Update script
        updated_script = "Updated script content with more information"
        digest_repo.update_script(digest_id, None, 20, updated_script)

        # Verify update
        retrieved_digest = digest_repo.get_by_id(digest_id)
        assert retrieved_digest.script_content == updated_script
        assert retrieved_digest.script_word_count == 20


class TestDatabaseMigrationIntegration:
    """Test end-to-end database storage integration"""

    def test_no_file_dependencies(self, episode_repo, digest_repo, sample_episode, sample_digest):
        """Test that database operations work without file system dependencies"""
        # Create episode and digest
        episode_id = episode_repo.create(sample_episode)
        digest_id = digest_repo.create(sample_digest)

        # Store content directly in database
        transcript_content = "Database-only transcript content"
        script_content = "Database-only script content"

        episode_repo.update_transcript(sample_episode.episode_guid, None, 50, transcript_content)
        digest_repo.update_script(digest_id, None, 30, script_content)

        # Verify both can be retrieved without file system
        episode = episode_repo.get_by_guid(sample_episode.episode_guid)
        digest = digest_repo.get_by_id(digest_id)

        assert episode.transcript_content == transcript_content
        assert digest.script_content == script_content

        # Verify no file paths are stored
        assert episode.transcript_path is None
        assert digest.script_path is None

    def test_unicode_and_special_characters(self, episode_repo, digest_repo, sample_episode, sample_digest):
        """Test handling of unicode and special characters in content"""
        episode_id = episode_repo.create(sample_episode)
        digest_id = digest_repo.create(sample_digest)

        # Content with various unicode characters
        unicode_transcript = """
Transcript with unicode:
- Español: ñáéíóú
- Chinese: 你好世界
- Emoji: 🎵🎤📻
- Mathematical: ∑∫∞≈
"""

        unicode_script = """
Script with special characters:
- Smart quotes: "Hello" 'World'
- Currency: $€£¥
- Symbols: ©®™
- Accents: café naïve résumé
"""

        episode_repo.update_transcript(sample_episode.episode_guid, None, 100, unicode_transcript)
        digest_repo.update_script(digest_id, None, 80, unicode_script)

        # Retrieve and verify unicode handling
        episode = episode_repo.get_by_guid(sample_episode.episode_guid)
        digest = digest_repo.get_by_id(digest_id)

        assert episode.transcript_content == unicode_transcript
        assert digest.script_content == unicode_script