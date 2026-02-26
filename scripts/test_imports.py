#!/usr/bin/env python3
"""
Pre-commit smoke test: verifies all pipeline modules import cleanly
and key classes can be instantiated without external API keys.

This catches import breakage from migration work (e.g., removing
openai/anthropic SDK imports without updating all references).

Exit code 0 = pass, 1 = fail.
"""

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load .env for DATABASE_URL (needed by WebConfigManager)
env_path = Path(project_root) / '.env'
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key, _, value = line.partition('=')
            os.environ.setdefault(key.strip(), value.strip())

FAIL = False


def check(label, fn):
    """Run a check function, print result, track failures."""
    global FAIL
    try:
        fn()
        print(f"  [PASS] {label}")
    except Exception as e:
        print(f"  [FAIL] {label}: {e}")
        FAIL = True


# ── Module imports ──────────────────────────────────────────────────
print("Module imports:")


def import_metadata_generator():
    from src.audio.metadata_generator import MetadataGenerator, EpisodeMetadata, MetadataGenerationError
    assert hasattr(MetadataGenerator, '_call_claude_p'), "Missing _call_claude_p"
    assert hasattr(MetadataGenerator, '_generate_metadata_with_claude_p'), "Missing _generate_metadata_with_claude_p"
    assert hasattr(MetadataGenerator, '_fetch_digest_episodes'), "Missing _fetch_digest_episodes"
    import dataclasses
    fields = {f.name for f in dataclasses.fields(EpisodeMetadata)}
    assert 'episode_links' in fields, "EpisodeMetadata missing episode_links field"


def import_content_scorer():
    from src.scoring.content_scorer import ContentScorer, ScoringResult
    assert hasattr(ContentScorer, '_call_claude_p'), "Missing _call_claude_p"
    assert hasattr(ContentScorer, '_score_with_claude_p'), "Missing _score_with_claude_p"
    assert hasattr(ContentScorer, '_load_scoring_skill'), "Missing _load_scoring_skill"


def import_script_generator():
    from src.generation.script_generator import ScriptGenerator
    assert hasattr(ScriptGenerator, '_call_claude_p'), "Missing _call_claude_p"
    assert hasattr(ScriptGenerator, '_build_claude_p_dialogue_prompt'), "Missing _build_claude_p_dialogue_prompt"


def import_audio_modules():
    from src.audio.audio_generator import AudioGenerator, ElevenLabsQuotaExceededError
    from src.audio.complete_audio_processor import CompleteAudioProcessor
    from src.audio.audio_manager import AudioManager
    assert issubclass(ElevenLabsQuotaExceededError, Exception), "ElevenLabsQuotaExceededError must be an Exception"
    assert hasattr(AudioGenerator, '_generate_dialogue_audio_openai'), "Missing OpenAI TTS dialogue fallback"
    assert hasattr(AudioGenerator, '_generate_narrative_audio_openai'), "Missing OpenAI TTS narrative fallback"


def import_pipeline_modules():
    from src.podcast.feed_parser import FeedParser
    from src.config.config_manager import ConfigManager
    from src.config.web_config import WebConfigManager


check("metadata_generator (claude -p methods + EpisodeMetadata.episode_links)", import_metadata_generator)
check("content_scorer (claude -p methods)", import_content_scorer)
check("script_generator (claude -p methods)", import_script_generator)
check("audio modules (AudioGenerator, CompleteAudioProcessor)", import_audio_modules)
check("pipeline modules (FeedParser, ConfigManager, WebConfigManager)", import_pipeline_modules)


# ── Instantiation without OPENAI_API_KEY ────────────────────────────
print("\nInstantiation (no OPENAI_API_KEY required):")

# Temporarily remove OPENAI_API_KEY to verify classes don't crash
saved_key = os.environ.pop('OPENAI_API_KEY', None)
try:
    def instantiate_metadata_generator():
        from src.audio.metadata_generator import MetadataGenerator
        mg = MetadataGenerator()
        assert mg is not None

    def instantiate_content_scorer():
        from src.scoring.content_scorer import ContentScorer
        cs = ContentScorer()
        assert cs is not None

    check("MetadataGenerator() without OPENAI_API_KEY", instantiate_metadata_generator)
    check("ContentScorer() without OPENAI_API_KEY", instantiate_content_scorer)
finally:
    if saved_key:
        os.environ['OPENAI_API_KEY'] = saved_key


# ── Skill files ─────────────────────────────────────────────────────
print("\nSkill files:")

SKILL_DIR = Path(project_root) / '.claude' / 'commands'

REQUIRED_SKILLS = [
    'generate-digest.md',
    'generate-metadata.md',
    'score-topic.md',
]

for skill_name in REQUIRED_SKILLS:
    def check_skill(name=skill_name):
        path = SKILL_DIR / name
        assert path.exists(), f"Skill file not found: {path}"
        content = path.read_text()
        assert len(content) > 100, f"Skill file suspiciously short ({len(content)} chars)"

    check(f"{skill_name} exists and has content", check_skill)


# ── Result ──────────────────────────────────────────────────────────
print()
if FAIL:
    print("FAILED: Some checks did not pass. Fix before committing.")
    sys.exit(1)
else:
    print("All pre-commit import checks passed.")
    sys.exit(0)
