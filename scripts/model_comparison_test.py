#!/usr/bin/env python3
"""
Multi-Model Digest Comparison Test Script

Compares digest generation quality across three models:
- GPT-5.2 (OpenAI) - with full context, no 20K truncation
- Claude Opus 4.5 (Anthropic) - extended thinking
- Gemini 3 Pro (Google) - thinking mode

Generates digests from the same episode transcripts and evaluates output quality.
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, date
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            key, _, value = line.partition('=')
            os.environ[key.strip()] = value.strip()

from src.database.models import get_database_manager
from src.database.sqlalchemy_models import Episode, Topic
from sqlalchemy import text


@dataclass
class ModelConfig:
    """Configuration for each model to test."""
    name: str
    provider: str
    model_id: str
    max_input_tokens: int
    supports_thinking: bool = False
    thinking_param: Optional[str] = None


@dataclass
class TestResult:
    """Results from a single model test."""
    model_name: str
    transcript_chars: int
    output_chars: int
    generation_time_seconds: float
    script_content: str
    error: Optional[str] = None


# Model configurations
MODELS = [
    ModelConfig(
        name="GPT-5.2",
        provider="openai",
        model_id="gpt-5.2",
        max_input_tokens=272000,
        supports_thinking=False
    ),
    ModelConfig(
        name="Claude Opus 4.5",
        provider="anthropic",
        model_id="claude-opus-4-5-20251101",
        max_input_tokens=200000,
        supports_thinking=True,
        thinking_param="extended"
    ),
    ModelConfig(
        name="Gemini 3 Pro",
        provider="google",
        model_id="gemini-3-pro-preview",
        max_input_tokens=1000000,
        supports_thinking=True,
        thinking_param="high"
    ),
]


def get_topic_instructions() -> str:
    """Get the AI and Technology topic instructions from database."""
    db_manager = get_database_manager()
    session = db_manager.get_session()

    topic = session.query(Topic).filter(Topic.name.ilike('%ai%tech%')).first()
    instructions = topic.instructions_md if topic else ""

    session.close()
    return instructions


def get_test_episodes(min_length: int = 40000, min_score: float = 0.7, limit: int = 4) -> List[Episode]:
    """Get episodes with long transcripts and high AI & Tech scores for testing."""
    db_manager = get_database_manager()
    session = db_manager.get_session()

    # Query for episodes with good AI & Tech scores and long transcripts
    episodes = session.query(Episode).filter(
        Episode.transcript_content.isnot(None),
        Episode.status.in_(['scored', 'digested'])
    ).all()

    # Filter by transcript length and AI score
    qualified = []
    for ep in episodes:
        if not ep.transcript_content or len(ep.transcript_content) < min_length:
            continue
        scores = ep.scores or {}
        ai_score = scores.get('AI and Technology', 0)
        if ai_score >= min_score:
            qualified.append((ep, len(ep.transcript_content), ai_score))

    # Sort by transcript length and take top N
    qualified.sort(key=lambda x: x[1], reverse=True)
    result = [ep for ep, _, _ in qualified[:limit]]

    session.close()
    return result


def build_prompt(episodes: List[Episode], topic_instructions: str, digest_date: date) -> Tuple[str, str]:
    """Build the system and user prompts for digest generation."""

    system_prompt = f"""You are a professional podcast script writer creating a conversational digest for the topic "AI and Technology".

DIALOGUE FORMAT (CRITICAL - EXACT FORMAT REQUIRED):
EVERY speaker turn MUST follow this EXACT format:

SPEAKER_1: [audio_tag] dialogue text here...
SPEAKER_2: [audio_tag] dialogue text here...

REQUIREMENTS:
1. Speaker label MUST be exactly "SPEAKER_1:" or "SPEAKER_2:" (with colon immediately after number)
2. Audio tag MUST come AFTER the colon, wrapped in square brackets [like_this]

CHARACTER ROLES:
- SPEAKER_1 (Host): Primary host, introduces topics, asks questions
- SPEAKER_2 (Analyst): Expert analyst, provides insights and analysis

TOPIC INSTRUCTIONS:
{topic_instructions}

REQUIREMENTS:
- Target 15,000-20,000 characters (this is measured in characters, not words)
- Create engaging dialogue between Host and Analyst
- Use audio tags liberally to add emotional warmth and expression
- Focus on the most important insights and developments
- Cover ALL episodes provided - do not skip any

Date: {digest_date.strftime('%B %d, %Y')}
Topic: AI and Technology
Episodes: {len(episodes)}"""

    user_prompt = f"""Create a dialogue-style digest script from these {len(episodes)} episode(s):

IMPORTANT - TRANSCRIPT AVAILABILITY:
You have COMPLETE access to ALL {len(episodes)} episode transcripts provided below. Each transcript contains the FULL content - nothing has been truncated. Discuss insights from the ENTIRE transcript, including content from the beginning, middle, and end of each episode.

"""

    for i, episode in enumerate(episodes, 1):
        transcript = episode.transcript_content or ""
        score = (episode.scores or {}).get('AI and Technology', 0)
        user_prompt += f"""Episode {i}: "{episode.title}" (Published: {episode.published_date.strftime('%Y-%m-%d')}, Relevance Score: {score:.2f})

Transcript ({len(transcript):,} characters - FULL TRANSCRIPT, NOT TRUNCATED):
{transcript}

---

"""

    user_prompt += f"""Generate a dialogue script between SPEAKER_1 (Host) and SPEAKER_2 (Analyst) that covers the key insights from ALL episodes.

REMINDER: You have full transcripts for ALL {len(episodes)} episodes above. Discuss each episode's content directly - do not claim any transcripts are missing or unavailable.

CRITICAL: Use EXACT format for EVERY turn:
SPEAKER_1: [audio_tag] dialogue text...
SPEAKER_2: [audio_tag] dialogue text...

Target 15,000-20,000 characters. Use audio tags like [excited], [thoughtful], [concerned], [hopeful], [curious]."""

    return system_prompt, user_prompt


def generate_with_openai(system_prompt: str, user_prompt: str, config: ModelConfig) -> TestResult:
    """Generate digest using OpenAI GPT-5.2."""
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    start_time = time.time()
    try:
        # Use the responses API for GPT-5.x
        response = client.responses.create(
            model=config.model_id,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            reasoning={"effort": "medium"},
            max_output_tokens=30000
        )

        script_content = response.output_text
        generation_time = time.time() - start_time

        return TestResult(
            model_name=config.name,
            transcript_chars=len(user_prompt),
            output_chars=len(script_content),
            generation_time_seconds=generation_time,
            script_content=script_content
        )
    except Exception as e:
        return TestResult(
            model_name=config.name,
            transcript_chars=len(user_prompt),
            output_chars=0,
            generation_time_seconds=time.time() - start_time,
            script_content="",
            error=str(e)
        )


def generate_with_anthropic(system_prompt: str, user_prompt: str, config: ModelConfig) -> TestResult:
    """Generate digest using Claude Opus 4.5 with extended thinking."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    start_time = time.time()
    try:
        response = client.messages.create(
            model=config.model_id,
            max_tokens=16000,
            thinking={
                "type": "enabled",
                "budget_tokens": 10000
            },
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        # Extract text from response (may have thinking blocks)
        script_content = ""
        for block in response.content:
            if hasattr(block, 'text'):
                script_content += block.text

        generation_time = time.time() - start_time

        return TestResult(
            model_name=config.name,
            transcript_chars=len(user_prompt),
            output_chars=len(script_content),
            generation_time_seconds=generation_time,
            script_content=script_content
        )
    except Exception as e:
        return TestResult(
            model_name=config.name,
            transcript_chars=len(user_prompt),
            output_chars=0,
            generation_time_seconds=time.time() - start_time,
            script_content="",
            error=str(e)
        )


def generate_with_google(system_prompt: str, user_prompt: str, config: ModelConfig) -> TestResult:
    """Generate digest using Gemini 3 Pro with thinking mode."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

    start_time = time.time()
    try:
        response = client.models.generate_content(
            model=config.model_id,
            contents=f"{system_prompt}\n\n{user_prompt}",
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(
                    thinking_level="HIGH"
                ),
                max_output_tokens=30000
            )
        )

        script_content = response.text
        generation_time = time.time() - start_time

        return TestResult(
            model_name=config.name,
            transcript_chars=len(user_prompt),
            output_chars=len(script_content),
            generation_time_seconds=generation_time,
            script_content=script_content
        )
    except Exception as e:
        return TestResult(
            model_name=config.name,
            transcript_chars=len(user_prompt),
            output_chars=0,
            generation_time_seconds=time.time() - start_time,
            script_content="",
            error=str(e)
        )


def run_comparison_test() -> Dict:
    """Run the comparison test across all models."""
    print("=" * 80)
    print("MULTI-MODEL DIGEST COMPARISON TEST")
    print("=" * 80)
    print()

    # Get test episodes
    print("1. Selecting test episodes...")
    episodes = get_test_episodes(min_length=40000, min_score=0.7, limit=4)

    if len(episodes) < 2:
        print("   Not enough qualifying episodes, lowering threshold...")
        episodes = get_test_episodes(min_length=25000, min_score=0.6, limit=4)

    if not episodes:
        print("   ERROR: No qualifying episodes found!")
        return {}

    total_chars = sum(len(ep.transcript_content or "") for ep in episodes)
    print(f"   Selected {len(episodes)} episodes with {total_chars:,} total transcript characters:")
    for i, ep in enumerate(episodes, 1):
        chars = len(ep.transcript_content or "")
        score = (ep.scores or {}).get('AI and Technology', 0)
        print(f"   {i}. {ep.title[:50]}... ({chars:,} chars, score: {score:.2f})")
    print()

    # Get topic instructions
    print("2. Loading topic instructions...")
    topic_instructions = get_topic_instructions()
    print(f"   Loaded {len(topic_instructions):,} chars of instructions")
    print()

    # Build prompts
    print("3. Building prompts (NO TRUNCATION)...")
    digest_date = date.today()
    system_prompt, user_prompt = build_prompt(episodes, topic_instructions, digest_date)
    print(f"   System prompt: {len(system_prompt):,} chars")
    print(f"   User prompt: {len(user_prompt):,} chars (includes full transcripts)")
    print()

    # Run tests for each model
    results = []
    print("4. Running model tests...")
    print()

    for config in MODELS:
        print(f"   Testing {config.name}...")
        print(f"   - Provider: {config.provider}")
        print(f"   - Model ID: {config.model_id}")
        print(f"   - Max input tokens: {config.max_input_tokens:,}")

        if config.provider == "openai":
            result = generate_with_openai(system_prompt, user_prompt, config)
        elif config.provider == "anthropic":
            result = generate_with_anthropic(system_prompt, user_prompt, config)
        elif config.provider == "google":
            result = generate_with_google(system_prompt, user_prompt, config)
        else:
            result = TestResult(
                model_name=config.name,
                transcript_chars=0,
                output_chars=0,
                generation_time_seconds=0,
                script_content="",
                error=f"Unknown provider: {config.provider}"
            )

        results.append(result)

        if result.error:
            print(f"   - ERROR: {result.error}")
        else:
            print(f"   - Output: {result.output_chars:,} chars")
            print(f"   - Time: {result.generation_time_seconds:.1f} seconds")
        print()

    # Save results
    print("5. Saving results...")
    output_dir = Path(__file__).parent.parent / 'data' / 'model_comparison'
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Save each script
    for result in results:
        if result.script_content:
            filename = f"{result.model_name.replace(' ', '_')}_{timestamp}.md"
            filepath = output_dir / filename
            filepath.write_text(result.script_content)
            print(f"   Saved: {filename}")

    # Save summary
    summary = {
        "test_date": timestamp,
        "episodes": [
            {
                "id": ep.id,
                "title": ep.title,
                "transcript_length": len(ep.transcript_content or ""),
                "ai_score": (ep.scores or {}).get('AI and Technology', 0)
            }
            for ep in episodes
        ],
        "total_transcript_chars": total_chars,
        "results": [
            {
                "model": r.model_name,
                "output_chars": r.output_chars,
                "generation_time_seconds": r.generation_time_seconds,
                "error": r.error
            }
            for r in results
        ]
    }

    summary_path = output_dir / f"summary_{timestamp}.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"   Saved: summary_{timestamp}.json")
    print()

    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print()
    print("Results saved to:", output_dir)
    print()

    # Print summary table
    print("RESULTS SUMMARY:")
    print("-" * 60)
    print(f"{'Model':<20} {'Output Chars':<15} {'Time (s)':<12} {'Status':<12}")
    print("-" * 60)
    for r in results:
        status = "ERROR" if r.error else "OK"
        print(f"{r.model_name:<20} {r.output_chars:<15,} {r.generation_time_seconds:<12.1f} {status:<12}")
    print("-" * 60)

    return summary


if __name__ == "__main__":
    run_comparison_test()
