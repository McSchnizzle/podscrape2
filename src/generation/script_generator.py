"""
Script Generator for RSS Podcast Transcript Digest System.
Generates topic-based digest scripts from scored episodes using GPT-5.
"""

import os
import json
import logging
from datetime import date, datetime, UTC
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
from openai import OpenAI
from dataclasses import dataclass
# import anthropic  # Removed: now using claude -p instead of direct API

from ..database.models import (
    Episode,
    get_episode_repo,
    Digest,
    get_digest_repo,
    TopicRepository,
    get_topic_repo,
    DigestEpisodeLink,
    get_digest_episode_link_repo,
)
from ..database.story_arc_repo import get_story_arc_repo
from ..topic_tracking.ad_filter import AdFilter
from ..config.config_manager import ConfigManager
from ..config.web_config import WebConfigManager, SettingsKeys

logger = logging.getLogger(__name__)

@dataclass
class TopicInstruction:
    """Topic instruction loaded from database or filesystem."""
    name: str
    filename: str
    content: str
    voice_id: str
    active: bool
    description: str
    voice_settings: Optional[Dict[str, Any]] = None
    topic_id: Optional[int] = None
    source: str = "file"
    # Multi-voice dialogue support (v1.79+)
    use_dialogue_api: bool = False
    dialogue_model: str = 'eleven_turbo_v2_5'
    voice_config: Optional[Dict[str, Any]] = None  # {"speaker_1": {...}, "speaker_2": {...}}

class ScriptGenerationError(Exception):
    """Raised when script generation fails"""
    pass

class ScriptGenerator:
    """
    Generates topic-based digest scripts from scored episodes using GPT-5.
    Loads instructions from digest_instructions/ directory and enforces word limits.
    """
    
    def __init__(self, config_manager: ConfigManager = None, web_config: WebConfigManager = None,
                 topic_repo: TopicRepository = None, digest_episode_link_repo = None):
        self.web_config = web_config
        self.topic_repo = topic_repo
        self.digest_episode_link_repo = digest_episode_link_repo

        self.config = config_manager or ConfigManager(web_config=web_config, topic_repo=self.topic_repo)
        self.episode_repo = get_episode_repo()
        self.digest_repo = get_digest_repo()
        if self.topic_repo is None:
            try:
                self.topic_repo = getattr(self.config, "topic_repo", None) or get_topic_repo()
            except Exception as exc:
                logger.debug("Topic repository unavailable, falling back to filesystem topics: %s", exc)
                self.topic_repo = None

        if self.digest_episode_link_repo is None:
            try:
                self.digest_episode_link_repo = get_digest_episode_link_repo()
            except Exception as exc:
                logger.debug("Digest episode link repository unavailable: %s", exc)
                self.digest_episode_link_repo = None

        # Initialize story arc repository for context and deduplication
        try:
            self.story_arc_repo = get_story_arc_repo()
        except Exception as exc:
            logger.debug("Story arc repository unavailable: %s", exc)
            self.story_arc_repo = None

        # Initialize ad filter for transcript cleaning
        try:
            self.ad_filter = AdFilter()
        except Exception as exc:
            logger.debug("Ad filter initialization failed: %s", exc)
            self.ad_filter = None

        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        # Per-digest episode cap (from web config if available)
        self.max_episodes_per_digest = 5
        if self.web_config:
            try:
                self.max_episodes_per_digest = int(self.web_config.get_setting(SettingsKeys.ContentFiltering.CATEGORY, SettingsKeys.ContentFiltering.MAX_EPISODES_PER_DIGEST, 5))
            except Exception:
                pass

        # Minimum episodes required to generate digest (from web config if available)
        self.min_episodes_per_digest = 1
        if self.web_config:
            try:
                self.min_episodes_per_digest = int(self.web_config.get_setting(SettingsKeys.ContentFiltering.CATEGORY, SettingsKeys.ContentFiltering.MIN_EPISODES_PER_DIGEST, 1))
            except Exception:
                pass
        
        # Load topic configuration
        self.topics = self.config.get_topics()
        self.score_threshold = self.config.get_score_threshold()
        self.max_words = self.config.get_max_words_per_script()

        # Load AI configuration for digest generation
        if self.web_config:
            self.ai_model = self.web_config.get_setting(SettingsKeys.AIDigestGeneration.CATEGORY, SettingsKeys.AIDigestGeneration.MODEL, 'gpt-5')
            self.max_output_tokens = self.web_config.get_setting(SettingsKeys.AIDigestGeneration.CATEGORY, SettingsKeys.AIDigestGeneration.MAX_OUTPUT_TOKENS, 25000)
            self.max_input_tokens = self.web_config.get_setting(SettingsKeys.AIDigestGeneration.CATEGORY, SettingsKeys.AIDigestGeneration.MAX_INPUT_TOKENS, 500000)

            # Load transcript limit settings (previously hardcoded, now from web config)
            self.transcript_min_chars = int(self.web_config.get_setting(
                SettingsKeys.AIDigestGeneration.CATEGORY,
                SettingsKeys.AIDigestGeneration.TRANSCRIPT_MIN_CHARS, 2000))
            self.transcript_max_chars = int(self.web_config.get_setting(
                SettingsKeys.AIDigestGeneration.CATEGORY,
                SettingsKeys.AIDigestGeneration.TRANSCRIPT_MAX_CHARS, 200000))  # Default to 200K, not 20K

            # Validate token limits against model capabilities
            self.max_output_tokens = self._validate_and_adjust_token_limit(self.ai_model, self.max_output_tokens, 'max_output')
            self.max_input_tokens = self._validate_and_adjust_token_limit(self.ai_model, self.max_input_tokens, 'max_input')
        else:
            self.ai_model = 'gpt-5'
            self.max_output_tokens = 25000
            self.max_input_tokens = 500000
            self.transcript_min_chars = 2000
            self.transcript_max_chars = 200000  # Default to 200K for full transcript support

        logger.info(
            'ScriptGenerator initialized with model: %s, max_output_tokens: %s, max_input_tokens: %s',
            self.ai_model,
            self.max_output_tokens,
            self.max_input_tokens,
        )

        # Load topic instructions
        self.topic_instructions = self._load_topic_instructions()

        # Create scripts directory
        self.scripts_dir = Path('data/scripts')
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_topic_instructions(self) -> Dict[str, TopicInstruction]:
        """Load topic instructions from database (single source of truth)"""
        instructions: Dict[str, TopicInstruction] = {}

        for topic in self.topics:
            if not topic.get('active', True):
                continue

            # Database-first architecture: all instructions must be in database
            instructions_md = topic.get('instructions_md')
            if not instructions_md or not instructions_md.strip():
                logger.error(f"Topic '{topic['name']}' has no instructions_md in database - system requires database content")
                raise ScriptGenerationError(f"Topic '{topic['name']}' missing instructions_md in database")

            instructions[topic['name']] = TopicInstruction(
                name=topic['name'],
                filename=topic.get('instruction_file') or f"{topic.get('slug') or topic['name'].replace(' ', '_')}.md",
                content=instructions_md,
                voice_id=topic.get('voice_id', ''),
                active=topic.get('active', True),
                description=topic.get('description', ''),
                voice_settings=topic.get('voice_settings'),
                topic_id=topic.get('id'),
                source='database',
                use_dialogue_api=topic.get('use_dialogue_api', False),
                dialogue_model=topic.get('dialogue_model', 'eleven_turbo_v2_5'),
                voice_config=topic.get('voice_config')
            )
            logger.info(f"Loaded instructions from database: {topic['name']} ({len(instructions_md)} chars)")

        logger.info(f"Loaded instructions for {len(instructions)} topics (database-first architecture)")
        return instructions

    def _is_anthropic_model(self, model: str = None) -> bool:
        """Check if the configured or given model is an Anthropic Claude model."""
        model = model or self.ai_model
        return model.startswith('claude-')

    def _get_model_provider(self, model: str = None) -> str:
        """Determine provider for a model name."""
        model = model or self.ai_model
        if model.startswith('claude-'):
            return 'anthropic'
        return 'openai'

    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ PREVIOUS IMPLEMENTATION: Direct Anthropic API client                │
    # │ To revert: uncomment _get_anthropic_client(), restore the          │
    # │ Anthropic streaming block in _call_llm(), and restore              │
    # │ 'import anthropic' at file top + self.anthropic_client in __init__.│
    # │                                                                     │
    # │ def _get_anthropic_client(self):                                    │
    # │     if self.anthropic_client is None:                               │
    # │         api_key = os.getenv('ANTHROPIC_API_KEY')                    │
    # │         if not api_key:                                             │
    # │             raise ScriptGenerationError("ANTHROPIC_API_KEY ...")    │
    # │         self.anthropic_client = anthropic.Anthropic(api_key=api_key)│
    # │     return self.anthropic_client                                    │
    # │                                                                     │
    # │ # In _call_llm, the Anthropic branch was:                           │
    # │ client = self._get_anthropic_client()                               │
    # │ output_text = ""                                                    │
    # │ with client.messages.stream(                                        │
    # │     model=self.ai_model,                                            │
    # │     max_tokens=int(self.max_output_tokens),                         │
    # │     system=system_prompt,                                           │
    # │     messages=[{"role": "user", "content": user_prompt}]             │
    # │ ) as stream:                                                        │
    # │     for text in stream.text_stream: output_text += text             │
    # │ return output_text                                                  │
    # └─────────────────────────────────────────────────────────────────────┘

    @staticmethod
    def _call_claude_p(system_prompt: str, user_prompt: str, timeout: int = 1200) -> str:
        """Call Claude via claude -p (programmatic mode) instead of direct API.

        Uses the Claude Code CLI's programmatic mode, which runs on the existing
        Claude subscription instead of per-token API billing.

        Prompt is passed via stdin to avoid OS argument length limits (ARG_MAX)
        since transcript content can be very large.

        Args:
            system_prompt: System-level instructions
            user_prompt: The user prompt to send
            timeout: Subprocess timeout in seconds (default 20 min for extended thinking)

        Returns:
            The text response from Claude
        """
        import subprocess

        claude_path = os.path.expanduser("~/.local/bin/claude")
        if not os.path.exists(claude_path):
            claude_path = "claude"  # Fall back to system PATH

        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        env = os.environ.copy()
        env.pop("CLAUDECODE", None)  # Allow running from within Claude Code context
        env.pop("ANTHROPIC_API_KEY", None)  # Force Max subscription, not API billing

        result = subprocess.run(
            [claude_path, "-p", "--model", "sonnet", "--effort", "low",
             "--tools", "", "--no-session-persistence", "-"],
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

        if result.returncode != 0:
            raise ScriptGenerationError(
                f"claude -p failed (exit {result.returncode}): {result.stderr[:500]}"
            )

        return result.stdout.strip()

    OPENAI_FALLBACK_MODEL = "gpt-5"

    def _call_openai_fallback(self, system_prompt: str, user_prompt: str) -> str:
        """Fallback to OpenAI API when claude -p fails or times out."""
        logger.info(f"Using OpenAI fallback model: {self.OPENAI_FALLBACK_MODEL}")
        response = self.openai_client.responses.create(
            model=self.OPENAI_FALLBACK_MODEL,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            reasoning={"effort": "medium"},
            max_output_tokens=25000
        )
        return response.output_text

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Route LLM call to the appropriate provider based on configured model.
        Falls back to OpenAI API if claude -p fails."""
        if self._is_anthropic_model():
            # v3.29: probe claude -p health before attempting; broken claude
            # subprocesses can hang for the full timeout (~6 min). The health
            # check costs us at most 20s once per process.
            try:
                from src.utils.claude_p_health import is_claude_p_healthy
                if not is_claude_p_healthy():
                    logger.warning("_call_llm: claude -p unhealthy, going straight to OpenAI fallback")
                    return self._call_openai_fallback(system_prompt, user_prompt)
            except Exception:
                pass
            logger.info("Using claude -p for Anthropic model call (no API key)")
            try:
                return self._call_claude_p(system_prompt, user_prompt)
            except (ScriptGenerationError, Exception) as e:
                logger.warning(f"claude -p failed in _call_llm, falling back to OpenAI: {e}")
                # v3.30: if the failure was a timeout, mark claude -p unhealthy
                if "timed out" in str(e).lower() or "TimeoutExpired" in type(e).__name__:
                    try:
                        from src.utils.claude_p_health import mark_unhealthy
                        mark_unhealthy("_call_llm script generation timeout")
                    except Exception:
                        pass
                return self._call_openai_fallback(system_prompt, user_prompt)
        else:
            response = self.openai_client.responses.create(
                model=self.ai_model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                reasoning={"effort": "medium"},
                max_output_tokens=self.max_output_tokens
            )
            return response.output_text

    def _validate_and_adjust_token_limit(self, model: str, requested_tokens: int, limit_type: str) -> int:
        """Validate and adjust token limit based on model capabilities"""
        if not self.web_config:
            return requested_tokens

        provider = self._get_model_provider(model)
        max_limit = self.web_config.get_model_limit(provider, model, limit_type)
        if max_limit > 0 and requested_tokens > max_limit:
            logger.warning(
                f"Requested {requested_tokens} {limit_type} tokens exceeds {model} limit of {max_limit}, adjusting to {max_limit}"
            )
            return max_limit

        return requested_tokens

    def _is_dialogue_mode(self, topic_name: str) -> bool:
        """
        Check if topic is configured for dialogue mode.

        Args:
            topic_name: Name of the topic to check

        Returns:
            True if topic uses dialogue API, False otherwise
        """
        instruction = self.topic_instructions.get(topic_name)
        if not instruction:
            return False
        return instruction.use_dialogue_api

    def _get_topic_config(self, topic_name: str) -> Optional[TopicInstruction]:
        """
        Get topic configuration including voice and dialogue settings.

        Args:
            topic_name: Name of the topic to retrieve

        Returns:
            TopicInstruction object or None if not found
        """
        return self.topic_instructions.get(topic_name)

    def _classify_story_arcs(self, arcs: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Classify arcs into 'hot' and 'developing' categories based on prominence.

        Classification thresholds:
        - Hot: is_hot flag set, OR 5+ events, OR 3+ sources (priority framing)
        - Developing: 2-4 events with 1-2 sources (standard tracking)

        Args:
            arcs: List of arc dictionaries from story_arc_repo

        Returns:
            Dict with 'hot' and 'developing' keys containing filtered arc lists
        """
        hot = []
        developing = []

        for arc in arcs:
            event_count = arc.get('event_count', 0)
            source_count = arc.get('source_count', 0)
            is_hot = arc.get('is_hot', False)

            # Hot: manually flagged, OR 5+ events, OR 3+ sources
            if is_hot or event_count >= 5 or source_count >= 3:
                hot.append(arc)
            # Developing: 2-4 events (already filtered by min_events=2 in query)
            elif event_count >= 2:
                developing.append(arc)

        # Sort by event count descending within each category
        hot.sort(key=lambda a: a.get('event_count', 0), reverse=True)
        developing.sort(key=lambda a: a.get('event_count', 0), reverse=True)

        logger.debug(f"Classified arcs: {len(hot)} hot, {len(developing)} developing")
        return {'hot': hot, 'developing': developing}

    def _match_arcs_to_episodes(self, arcs: List[Dict], episodes: List[Episode]) -> List[Dict]:
        """
        Filter arcs to only those with supporting evidence in episode transcripts.

        Uses semantic embedding similarity when available, with keyword fallback.
        This prevents hallucinations by ensuring GPT only references arcs that
        have actual content in the provided episodes.

        Args:
            arcs: List of arc dictionaries
            episodes: List of episodes with transcript_content

        Returns:
            List of arcs enriched with 'supporting_episodes' field,
            filtered to only arcs with at least one supporting episode
        """
        if not arcs or not episodes:
            return []

        # Try embedding-based grounding first
        grounded_arcs = self._match_arcs_via_embeddings(arcs, episodes)
        if grounded_arcs is not None:
            return grounded_arcs

        # Fallback to keyword matching
        return self._match_arcs_via_keywords(arcs, episodes)

    def _match_arcs_via_embeddings(self, arcs: List[Dict], episodes: List[Episode]) -> Optional[List[Dict]]:
        """
        Match arcs to episodes using semantic embedding similarity.
        Returns None if embeddings are unavailable (triggers keyword fallback).
        """
        try:
            from src.topic_tracking.semantic_matcher import SemanticTopicMatcher
            matcher = SemanticTopicMatcher()

            # Build episode text snippets (first 2000 chars of transcript for efficiency)
            episode_texts = []
            episode_titles = []
            for ep in episodes:
                transcript = (ep.transcript_content or '')[:2000]
                if transcript:
                    episode_texts.append(f"{ep.title}: {transcript}")
                    episode_titles.append(ep.title)

            if not episode_texts:
                return []

            # Get episode embeddings
            episode_embeddings = [matcher._get_embedding(text) for text in episode_texts]

            grounded_arcs = []
            similarity_threshold = 0.35  # Lower threshold for arc-to-transcript matching

            for arc in arcs:
                arc_name = arc.get('arc_name', '')
                # Include recent event summaries for richer arc representation
                events = arc.get('events', [])
                event_text = ' '.join(e.get('event_summary', '')[:100] for e in events[:3])
                arc_text = f"{arc_name} {event_text}".strip()

                if not arc_text:
                    continue

                arc_embedding = matcher._get_embedding(arc_text)

                # Find supporting episodes
                supporting_episodes = []
                for i, ep_emb in enumerate(episode_embeddings):
                    similarity = matcher._cosine_similarity(arc_embedding, ep_emb)
                    if similarity >= similarity_threshold:
                        supporting_episodes.append(episode_titles[i])

                if supporting_episodes:
                    arc_copy = arc.copy()
                    arc_copy['supporting_episodes'] = supporting_episodes[:3]
                    grounded_arcs.append(arc_copy)

            logger.info(f"Story arc grounding (embeddings): {len(grounded_arcs)}/{len(arcs)} arcs have supporting episodes")
            return grounded_arcs

        except Exception as e:
            logger.warning(f"Embedding-based arc grounding failed, falling back to keywords: {e}")
            return None

    def _match_arcs_via_keywords(self, arcs: List[Dict], episodes: List[Episode]) -> List[Dict]:
        """Fallback keyword-based arc matching."""
        grounded_arcs = []

        for arc in arcs:
            arc_name = arc.get('arc_name', '')
            key_terms = self._extract_arc_key_terms(arc_name)

            if not key_terms:
                continue

            # Find episodes that contain key terms
            supporting_episodes = []
            for episode in episodes:
                transcript = (episode.transcript_content or '').lower()
                if not transcript:
                    continue

                # Check if enough key terms appear in transcript
                matches = sum(1 for term in key_terms if term in transcript)
                min_matches = 1 if len(key_terms) <= 2 else 2

                if matches >= min_matches:
                    supporting_episodes.append(episode.title)

            # Only include arc if it has supporting evidence
            if supporting_episodes:
                arc_copy = arc.copy()
                arc_copy['supporting_episodes'] = supporting_episodes[:3]
                grounded_arcs.append(arc_copy)

        logger.info(f"Story arc grounding (keywords): {len(grounded_arcs)}/{len(arcs)} arcs have supporting episodes")
        return grounded_arcs

    def _normalize_arc_name_for_tts(self, arc_name: str) -> str:
        """
        Convert arc name to TTS-safe spoken form for narrative mode.

        Handles common abbreviations and formatting that TTS systems struggle with.

        Args:
            arc_name: Raw arc name (e.g., "GPT-4 vs Claude AI Benchmark")

        Returns:
            TTS-normalized name (e.g., "G P T four vs Claude A I Benchmark")
        """
        import re

        result = arc_name

        # Common AI/tech abbreviations to expand
        abbreviations = {
            r'\bAI\b': 'A I',
            r'\bGPT-5\b': 'G P T five',
            r'\bGPT-4\b': 'G P T four',
            r'\bGPT-4o\b': 'G P T four oh',
            r'\bGPT\b': 'G P T',
            r'\bLLM\b': 'L L M',
            r'\bLLMs\b': 'L L Ms',
            r'\bAPI\b': 'A P I',
            r'\bAPIs\b': 'A P Is',
            r'\bML\b': 'M L',
            r'\bNLP\b': 'N L P',
            r'\bCEO\b': 'C E O',
            r'\bCTO\b': 'C T O',
            r'\bIPO\b': 'I P O',
            r'\bUS\b': 'U S',
            r'\bU\.S\.\b': 'U S',
            r'\bEU\b': 'E U',
            r'\bUK\b': 'U K',
        }

        for pattern, replacement in abbreviations.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        return result

    def _calculate_transcript_limit(self, num_episodes: int, arc_context_length: int = 0) -> int:
        """
        Calculate transcript character limit based on configured input token cap and web settings.

        Args:
            num_episodes: Number of episodes to divide budget across
            arc_context_length: Length of story arc context in chars (reserves tokens)

        Returns:
            Character limit per episode transcript
        """
        if not getattr(self, 'max_input_tokens', None):
            return 8000

        # Get limits from web settings (loaded in __init__)
        min_chars = getattr(self, 'transcript_min_chars', 2000)
        max_chars = getattr(self, 'transcript_max_chars', 200000)

        # Reserve tokens for: system prompt (~2k tokens), arc context, repetition instructions
        # Arc context chars / 4 = approximate tokens
        reserved_tokens = 3000 + (arc_context_length // 4)

        # Calculate available space based on input token budget minus reserved
        available_input_tokens = int(self.max_input_tokens * 0.8) - reserved_tokens
        available_input_tokens = max(available_input_tokens, 10000)  # Floor to prevent negative

        available_chars = available_input_tokens * 4
        chars_per_episode = available_chars // max(num_episodes, 1)

        # Apply configurable min/max limits from web settings
        return min(max(chars_per_episode, min_chars), max_chars)

    def _get_recent_story_arc_context(
        self,
        digest_topic: str,
        episodes: Optional[List[Episode]] = None,
        days_back: int = None,
        for_narrative: bool = False
    ) -> str:
        """
        Retrieve active story arcs with grounding and classification.

        Args:
            digest_topic: Name of the digest topic (e.g., "AI and Technology")
            episodes: List of episodes for grounding (filters to supported arcs only)
            days_back: Number of days to look back (default from config)
            for_narrative: If True, include TTS-normalized arc names

        Returns:
            Formatted string of active story arcs for GPT prompt (max 4000 chars)
        """
        MAX_CONTEXT_CHARS = 4000  # Cap to prevent token overflow

        if not self.story_arc_repo:
            logger.debug("Story arc repository unavailable, skipping context")
            return ""

        # Get lookback window from config
        if days_back is None:
            if self.web_config:
                days_back = self.web_config.get_setting(
                    SettingsKeys.TopicTracking.CATEGORY,
                    SettingsKeys.TopicTracking.RETENTION_DAYS,
                    14
                )
            else:
                days_back = 14

        try:
            # Get story arcs that haven't been included yet
            arcs = self.story_arc_repo.get_story_arcs_for_digest(
                digest_topic=digest_topic,
                min_events=2,           # Only arcs with multiple events
                exclude_included=False  # Include all for context (mark after generation)
            )

            # Query hot arcs separately (no min_events filter -- always include)
            hot_flag_arcs = self.story_arc_repo.get_story_arcs_for_digest(
                digest_topic=digest_topic,
                min_events=0,
                exclude_included=False
            )
            hot_flag_arcs = [a for a in hot_flag_arcs if a.get('is_hot', False)]

            # Merge hot arcs into the main list, deduplicating by arc ID
            existing_ids = {a.get('id') for a in arcs}
            for ha in hot_flag_arcs:
                if ha.get('id') not in existing_ids:
                    arcs.append(ha)
                    existing_ids.add(ha.get('id'))

            if not arcs:
                logger.debug(f"No active story arcs found for {digest_topic}")
                return ""

            # Ground arcs to episodes if provided (prevents hallucinations)
            # Hot arcs bypass grounding -- they are always included
            if episodes:
                grounded_arcs = self._match_arcs_to_episodes(arcs, episodes)
                # Re-add hot-flagged arcs that were filtered out by grounding
                grounded_ids = {a.get('id') for a in grounded_arcs}
                for arc in arcs:
                    if arc.get('is_hot', False) and arc.get('id') not in grounded_ids:
                        grounded_arcs.append(arc)
                arcs = grounded_arcs
                if not arcs:
                    logger.info(f"No story arcs have supporting evidence in episodes for {digest_topic}")
                    return ""

            # Deprioritize saturated arcs (covered 3+ times) by sorting them lower
            arcs.sort(key=lambda a: a.get('saturation_score', 0.0))

            # v3.27: explicitly identify saturated arcs so the prompt can warn
            # the model away from re-introducing them. saturation_score >= 0.9
            # means the arc has been covered ~3+ times.
            saturated_arcs = [
                a for a in arcs if (a.get('saturation_score') or 0.0) >= 0.9
            ]

            # Classify into hot/developing
            classified = self._classify_story_arcs(arcs)
            hot_arcs = classified['hot']
            developing_arcs = classified['developing']

            # Build hot briefing section first (prioritized for token budget)
            hot_briefing_section = ""
            briefing_arcs = [
                a for a in arcs
                if a.get('is_hot', False) and a.get('hot_briefing')
            ]
            if briefing_arcs:
                hot_briefing_section = "\n\n## HOT STORY BRIEFINGS\n\n"
                for arc in briefing_arcs:
                    arc_name = arc.get('arc_name', '')
                    category = arc.get('functional_category', 'other')
                    event_count = arc.get('event_count', 0)
                    source_count = arc.get('source_count', 0)
                    briefing = arc.get('hot_briefing', '')
                    hot_briefing_section += f"### {arc_name}\n"
                    hot_briefing_section += f"Category: {category} | Events: {event_count} | Sources: {source_count}\n"
                    hot_briefing_section += f"BRIEFING: {briefing}\n"
                    hot_briefing_section += (
                        "FRAMING: This is a story we are actively tracking. "
                        "Here is the accumulated briefing. Use this to contextualize "
                        "any new developments. Do NOT re-introduce the story -- our "
                        "audience knows the background. Focus on what's NEW.\n\n"
                    )

            # Build context with new framing
            context = "\n\n## STORY ARC INTEGRATION\n\n"
            context += "This digest is part of an ongoing series. The following story arcs have "
            if episodes:
                context += "supporting evidence in today's episodes:\n\n"
            else:
                context += "been tracked recently:\n\n"

            # Hot stories section
            if hot_arcs:
                context += "**HOT STORIES** (flagged, 5+ events, OR 3+ sources - PRIORITY):\n\n"
                for arc in hot_arcs[:5]:  # Limit to top 5 hot
                    context += self._format_arc_for_context(arc, for_narrative)

            # Developing stories section
            if developing_arcs:
                context += "**DEVELOPING STORIES**:\n\n"
                for arc in developing_arcs[:5]:  # Limit to top 5 developing
                    context += self._format_arc_for_context(arc, for_narrative)

            # v3.32: Saturated arcs are stories covered 3+ times. Instead of
            # suppressing them entirely (which drops new angles), we tell the
            # model to skip repeated facts but still find new information.
            if saturated_arcs:
                context += "\n**WELL-COVERED STORIES** (covered 3+ times — audience knows the basics):\n\n"
                for arc in saturated_arcs[:8]:
                    arc_name = arc.get('arc_name', '')
                    if for_narrative:
                        arc_name = self._normalize_arc_name_for_tts(arc_name)
                    context += f"- {arc_name}\n"
                context += (
                    "\nFor WELL-COVERED stories: our audience knows the background. "
                    "Do NOT re-explain the basics or repeat statistics/facts from prior "
                    "episodes. Instead, look for genuinely new information in today's "
                    "transcripts: a new source's reaction, new data, a consequence, or "
                    "a different angle. If you find something new, frame it as an update "
                    "(e.g., 'New development on the Glasswing story...'). If there is "
                    "truly NOTHING new, briefly note that sources continue to cover it "
                    "and move on — do not skip the topic entirely.\n"
                )

            # Add framing instructions
            context += """\n**FRAMING INSTRUCTIONS:**
1. When covering content related to a story arc, reference it naturally
2. Use phrases like "In the ongoing [topic] story..." or "Building on recent coverage..."
3. ONLY reference arcs that have supporting evidence in the transcripts above
4. If an arc has no new developments in today's content, do not force a mention
5. For previously covered arcs, focus on what's NEW - don't rehash background
"""

            # Combine: hot briefings first (highest priority), then arc context
            if hot_briefing_section:
                full_context = hot_briefing_section + context
            else:
                full_context = context

            # Truncate if too long, prioritizing hot briefings
            if len(full_context) > MAX_CONTEXT_CHARS:
                if hot_briefing_section:
                    # If briefings alone fit, truncate the arc context portion
                    remaining = MAX_CONTEXT_CHARS - len(hot_briefing_section) - 50
                    if remaining > 200:
                        full_context = hot_briefing_section + context[:remaining] + "\n\n[Arc context truncated for length]\n"
                    else:
                        # Briefings themselves are too long, truncate them
                        full_context = hot_briefing_section[:MAX_CONTEXT_CHARS - 50] + "\n\n[Context truncated for length]\n"
                else:
                    full_context = full_context[:MAX_CONTEXT_CHARS - 50] + "\n\n[Context truncated for length]\n"
                logger.warning(f"Story arc context truncated to {MAX_CONTEXT_CHARS} chars")

            logger.info(
                f"Arc context generated: {len(full_context)} chars, "
                f"{len(hot_arcs)} hot, {len(developing_arcs)} developing, "
                f"{len(briefing_arcs)} with briefings"
            )
            return full_context

        except Exception as e:
            logger.warning(f"Failed to retrieve story arc context for {digest_topic}: {e}")
            return ""

    def _format_arc_for_context(self, arc: Dict, for_narrative: bool = False) -> str:
        """Format a single arc for inclusion in the prompt context."""
        arc_name = arc.get('arc_name', '')
        category = arc.get('functional_category', 'other')
        event_count = arc.get('event_count', 0)
        source_count = arc.get('source_count', 0)
        supporting = arc.get('supporting_episodes', [])

        result = f"### {arc_name}\n"

        # Add TTS-safe name for narrative mode
        if for_narrative:
            tts_name = self._normalize_arc_name_for_tts(arc_name)
            if tts_name != arc_name:
                result += f"(Spoken: \"{tts_name}\")\n"

        result += f"Category: {category} | Events: {event_count} | Sources: {source_count}\n"

        # Show which episodes support this arc
        if supporting:
            result += f"Supported by: {', '.join(f'\"{ep}\"' for ep in supporting[:2])}\n"

        # Include recent events for context (limit to 2 for brevity)
        events = arc.get('events', [])
        if events:
            result += "Recent: "
            event_summaries = [e.get('event_summary', '')[:80] for e in events[:2]]
            result += "; ".join(event_summaries) + "\n"

        result += "\n"
        return result

    def _extract_arc_key_terms(self, arc_name: str) -> List[str]:
        """
        Extract searchable key terms from a story arc name.

        Extracts company names, product names, and significant phrases that
        would indicate the arc is being discussed in a script.

        Args:
            arc_name: Full arc name like "OpenAI Introduces Advertising Into ChatGPT"

        Returns:
            List of key terms to search for (e.g., ["openai", "chatgpt", "advertising"])
        """
        import re

        # Known entities to always extract (case-insensitive matching)
        known_entities = [
            'openai', 'anthropic', 'google', 'microsoft', 'meta', 'apple', 'amazon', 'nvidia',
            'chatgpt', 'gpt-5', 'gpt-4', 'claude', 'gemini', 'grok', 'copilot', 'siri',
            'deepmind', 'deepseek', 'mistral', 'llama', 'qwen',
            'tiktok', 'twitter', 'x.com',
        ]

        arc_lower = arc_name.lower()
        terms = []

        # Extract known entities
        for entity in known_entities:
            if entity in arc_lower:
                terms.append(entity)

        # Extract capitalized multi-word phrases (likely product/project names)
        # e.g., "Claude Code", "Vibe Coding", "Ralph Loop"
        words = arc_name.split()
        for i, word in enumerate(words):
            # Skip common words
            if word.lower() in ['the', 'a', 'an', 'of', 'in', 'to', 'for', 'and', 'or', 'as', 'by', 'on', 'with']:
                continue
            # Two-word capitalized phrases
            if i < len(words) - 1 and word[0].isupper() and words[i+1][0].isupper():
                phrase = f"{word} {words[i+1]}".lower()
                if phrase not in terms and len(phrase) > 5:
                    terms.append(phrase)

        # Extract significant single words (capitalized, not common)
        common_words = {
            'new', 'launches', 'introduces', 'emerges', 'becomes', 'expands', 'evolves',
            'into', 'from', 'over', 'under', 'through', 'about', 'against', 'between',
            'strategy', 'system', 'systems', 'platform', 'model', 'models', 'release',
            'industry', 'trend', 'trends', 'adoption', 'development', 'technology',
        }
        for word in words:
            if len(word) > 4 and word[0].isupper() and word.lower() not in common_words:
                if word.lower() not in terms:
                    terms.append(word.lower())

        # Ensure we have at least some terms
        if not terms:
            # Fallback: use significant words from the arc name
            for word in words:
                if len(word) > 5 and word.lower() not in common_words:
                    terms.append(word.lower())
                    if len(terms) >= 2:
                        break

        return terms[:5]  # Limit to 5 key terms

    def _arc_matches_script(self, arc_name: str, key_terms: List[str], script_lower: str) -> bool:
        """
        Check if an arc's key terms appear in the script content.

        Uses a scoring approach: arc is considered covered if enough
        key terms appear in the script.

        Args:
            arc_name: Full arc name
            key_terms: List of key terms extracted from arc name
            script_lower: Lowercase script content

        Returns:
            True if arc appears to be covered in the script
        """
        if not key_terms:
            return False

        # Count how many key terms appear
        matches = sum(1 for term in key_terms if term in script_lower)

        # Require at least 2 matches, or 1 match if only 1-2 terms
        if len(key_terms) <= 2:
            return matches >= 1
        else:
            return matches >= 2

    def mark_covered_story_arcs(self, digest_id: int, digest_topic: str, script_content: str) -> int:
        """
        Mark story arcs as included in the digest based on content analysis.

        Uses key term extraction to find arcs discussed in the script,
        rather than exact arc name matching.

        Args:
            digest_id: The database ID of the generated digest
            digest_topic: The topic name
            script_content: The generated script content

        Returns:
            Number of arcs marked as included
        """
        if not self.story_arc_repo:
            return 0

        try:
            # Get all active arcs
            arcs = self.story_arc_repo.get_story_arcs_for_digest(
                digest_topic=digest_topic,
                min_events=1,
                exclude_included=False  # Track all arcs across multiple digests
            )

            script_lower = script_content.lower()
            arcs_marked = 0

            for arc in arcs:
                arc_name = arc.get('arc_name', '')
                key_terms = self._extract_arc_key_terms(arc_name)

                # Check if key terms appear in script
                if self._arc_matches_script(arc_name, key_terms, script_lower):
                    self.story_arc_repo.mark_story_arc_included(
                        story_arc_id=arc['id'],
                        digest_id=digest_id
                    )
                    arcs_marked += 1
                    logger.debug(f"Marked arc '{arc_name}' as included in digest {digest_id} (terms: {key_terms})")

            if arcs_marked > 0:
                logger.info(f"Marked {arcs_marked} story arcs as included in digest {digest_id}")

            return arcs_marked

        except Exception as e:
            logger.warning(f"Failed to mark story arcs as included: {e}")
            return 0

    def _build_repetition_avoidance_instructions(self, recently_covered_arcs: List[str], topic: str = "AI and Technology") -> str:
        """
        Build lightweight repetition avoidance instructions.

        Since v3.34, transcripts are pre-deduped before reaching the script
        generator, so we no longer need to include full prior digest snippets
        in the prompt. Just a short note that the transcripts have been
        pre-filtered for novelty.

        Args:
            recently_covered_arcs: List of arc names recently covered
            topic: Topic name (unused but kept for interface compatibility)

        Returns:
            Formatted string with repetition avoidance instructions
        """
        if not recently_covered_arcs:
            return ""

        return """

## PRE-FILTERED TRANSCRIPTS

These transcripts have been pre-filtered to remove content that was already
covered in recent episodes. The material you see below is what's NEW and
hasn't been reported to our audience yet. Cover it thoroughly — every
transcript provided has unique content worth discussing.

Do NOT skip any episode or treat any content as "old news" — if it's in
the transcript, it survived the dedup filter because it's genuinely new.
"""

    def _build_claude_p_dialogue_prompt(
        self,
        system_prompt: str,
        topic: str,
        topic_instructions: str,
        story_arc_context: str,
        repetition_instructions: str,
        digest_date: date,
        speaker_1_name: str,
        speaker_2_name: str,
        num_episodes: int,
    ) -> str:
        """Build the system prompt for claude -p dialogue generation.

        Loads the tuned skill file (.claude/commands/generate-digest.md) as the
        base, then injects the dynamic parts: topic instructions, story arc
        context, and repetition avoidance. This separates prompt engineering
        (the skill file) from pipeline logic (this method).

        Falls back to the hardcoded system_prompt if the skill file is not found.
        """
        skill_path = Path(__file__).parent.parent.parent / '.claude' / 'commands' / 'generate-digest.md'

        if skill_path.exists():
            skill_content = skill_path.read_text()
            logger.info(f"Loaded dialogue skill from {skill_path.name} ({len(skill_content)} chars)")
        else:
            logger.warning(f"Skill file not found at {skill_path}, falling back to hardcoded prompt")
            return system_prompt

        return (
            f"{skill_content}\n\n"
            f"## Topic-Specific Instructions\n{topic_instructions}\n\n"
            f"**PRE-FILTERED TRANSCRIPTS:** These transcripts have been pre-filtered "
            f"to remove content already covered in recent episodes. Everything provided "
            f"is NEW material. Cover it all thoroughly.\n\n"
            f"Date: {digest_date.strftime('%B %d, %Y')}\n"
            f"Topic: {topic}\n"
            f"Episodes: {num_episodes}\n\n"
            f"CHARACTER ROLES:\n"
            f"- SPEAKER_1 ({speaker_1_name}): Primary host, introduces topics, asks questions\n"
            f"- SPEAKER_2 ({speaker_2_name}): Expert analyst, provides insights and analysis"
        )

    def _generate_dialogue_script(self, topic: str, episodes: List[Episode],
                                  digest_date: date, instruction: TopicInstruction,
                                  recently_covered_arcs: Optional[List[str]] = None) -> Tuple[str, int]:
        """
        Generate dialogue-style script for multi-voice delivery (v3 with audio tags).
        Target: 25,000-30,000 characters with SPEAKER_1/SPEAKER_2 labels.

        Args:
            topic: Topic name
            episodes: List of episodes to include
            digest_date: Date of digest
            instruction: Topic configuration with voice_config
            recently_covered_arcs: Optional list of arc names recently covered.
                If provided, prompts include instructions to focus on NEW content.

        Returns:
            Tuple of (script_content, character_count)
        """
        # Extract speaker names from voice_config
        speaker_1_name = "Host"
        speaker_2_name = "Analyst"
        if instruction.voice_config:
            speaker_1 = instruction.voice_config.get('speaker_1', {})
            speaker_2 = instruction.voice_config.get('speaker_2', {})
            speaker_1_name = speaker_1.get('name', speaker_1.get('role', 'Host'))
            speaker_2_name = speaker_2.get('name', speaker_2.get('role', 'Analyst'))

        # Prepare episode transcripts
        transcripts = []
        total_ads_filtered = 0
        for episode in episodes:
            if not episode.transcript_content or not episode.transcript_content.strip():
                logger.error(f"No transcript content in database for episode: {episode.title}")
                raise ScriptGenerationError(f"Episode {episode.title} has no transcript content in database")

            # Apply ad filtering if available
            transcript_content = episode.transcript_content
            if self.ad_filter:
                transcript_content, detected_ads = self.ad_filter.filter_transcript(transcript_content)
                if detected_ads:
                    total_ads_filtered += len(detected_ads)
                    logger.info(f"Filtered {len(detected_ads)} ad types from '{episode.title}': {', '.join(detected_ads)}")

            transcripts.append({
                'title': episode.title,
                'published_date': episode.published_date.strftime('%Y-%m-%d'),
                'transcript': transcript_content,
                'score': episode.scores.get(topic, 0.0) if episode.scores else 0.0
            })

        if total_ads_filtered > 0:
            logger.info(f"Total ad filtering: {total_ads_filtered} ad types removed from {len(episodes)} episodes")

        # Retrieve active story arcs FIRST (need length for token budget)
        story_arc_context = self._get_recent_story_arc_context(
            topic,
            episodes=episodes,  # Ground arcs to episode content
            for_narrative=False
        )

        # Build repetition avoidance instructions if arcs were recently covered
        repetition_instructions = ""
        if recently_covered_arcs:
            repetition_instructions = self._build_repetition_avoidance_instructions(recently_covered_arcs, topic=topic)
            logger.info(f"Adding repetition avoidance for {len(recently_covered_arcs)} recently covered arcs")

        # Calculate transcript limit with arc context reserved
        arc_context_length = len(story_arc_context) + len(repetition_instructions)
        transcript_limit = self._calculate_transcript_limit(len(transcripts), arc_context_length)

        # Generate dialogue script with audio tags for ElevenLabs v3
        system_prompt = f"""You are a professional podcast script writer creating a conversational digest for the topic "{topic}".

DIALOGUE FORMAT (CRITICAL - EXACT FORMAT REQUIRED):
EVERY speaker turn MUST follow this EXACT format:

SPEAKER_1: [audio_tag] dialogue text here...
SPEAKER_2: [audio_tag] dialogue text here...

REQUIREMENTS:
1. Speaker label MUST be exactly "SPEAKER_1:" or "SPEAKER_2:" (with colon immediately after number)
2. Colon comes IMMEDIATELY after speaker number, BEFORE any audio tags
3. Audio tag MUST come AFTER the colon, wrapped in square brackets [like_this]
4. NO speaker names, NO parentheses, NO brackets before the colon

CORRECT FORMAT:
SPEAKER_1: [excited] This is a groundbreaking development!
SPEAKER_2: [thoughtful] Let me think about the implications here...
SPEAKER_1: [concerned] This raises some important questions.
SPEAKER_2: [hopeful] But there's reason for optimism.

INCORRECT FORMATS (DO NOT USE):
❌ SPEAKER_1 [excited] text... (missing colon)
❌ SPEAKER_1 [excited]: text... (colon after tag)
❌ Host 1: text... (wrong speaker name)
❌ SPEAKER_1 (Jamal): text... (name before colon)

CHARACTER ROLES:
- SPEAKER_1 ({speaker_1_name}): Primary host, introduces topics, asks questions
- SPEAKER_2 ({speaker_2_name}): Expert analyst, provides insights and analysis
- Create natural, engaging conversation with back-and-forth exchanges

TOPIC INSTRUCTIONS:
{instruction.content}

**PRE-FILTERED TRANSCRIPTS:**
These transcripts have been pre-filtered to remove content already covered in
recent episodes. Everything below is NEW material. Cover it all thoroughly.

REQUIREMENTS:
- Target 25,000-30,000 characters (this is measured in characters, not words)
- Create engaging dialogue between {speaker_1_name} and {speaker_2_name}
- Use audio tags sparingly — MAX 25 total, MAX 35% of turns tagged
- Follow the structure and anti-AI rules outlined in the topic instructions
- Include episode titles and dates when relevant
- Hosts are curators — attribute opinions to sources, do not manufacture disagreements

**EPISODE BREADTH REQUIREMENT (CRITICAL):**
Every episode transcript provided below MUST contribute at least one distinct
segment, insight, or data point to the digest. Do NOT fixate on 3-4 episodes
and ignore the rest. If an episode covers a familiar topic, find the angle,
detail, source perspective, or data point that IS unique to that episode.
Even a brief 2-3 sentence mention is better than ignoring an episode entirely.

Date: {digest_date.strftime('%B %d, %Y')}
Topic: {topic}
Episodes: {len(transcripts)}"""

        user_prompt = f"""Create a dialogue-style digest script from these {len(transcripts)} episode(s):

IMPORTANT - TRANSCRIPT AVAILABILITY:
You have COMPLETE access to ALL {len(transcripts)} episode transcripts provided below. Each transcript contains the full content needed to discuss that episode in detail. DO NOT claim you don't have access to any transcript, as all transcripts are fully provided. If a transcript seems shorter, it's because the episode itself was shorter or content was truncated for length - the key insights are present.

"""

        for i, transcript_data in enumerate(transcripts, 1):
            user_prompt += f"""Episode {i}: "{transcript_data['title']}" (Published: {transcript_data['published_date']}, Relevance Score: {transcript_data['score']:.2f})

Transcript:
{transcript_data['transcript'][:transcript_limit]}

---

"""

        user_prompt += f"""Generate a dialogue script between SPEAKER_1 ({speaker_1_name}) and SPEAKER_2 ({speaker_2_name}) that covers the key insights from these episodes.

REMINDER: You have full transcripts for ALL {len(transcripts)} episodes above. Discuss each episode's content directly based on the transcript provided - do not claim any transcripts are missing or unavailable.

CRITICAL FORMAT: Use EXACT format for EVERY turn:
SPEAKER_1: [audio_tag] dialogue text...
SPEAKER_2: [audio_tag] dialogue text...
The colon MUST come immediately after the speaker number, BEFORE the audio tag.

Follow ALL rules in the system prompt exactly, especially:
- Target 25,000-30,000 characters (NOT more)
- MAX 25 audio tags total, MAX 35% of turns tagged
- MAX 15 em dashes in the entire script — use commas, colons, semicolons, parentheses instead
- Do NOT manufacture disagreements between hosts — they are curators, not pundits. Attribute opinions to sources.
- NEVER use these phrases: "genuinely" (as intensifier), "throughline," "connect the threads," "what surprised you/us," "I want to push back," "both things can be true"
- Vary the episode structure — do NOT follow the same template every time"""

        try:
            used_fallback = False
            if self._is_anthropic_model():
                # For claude -p path: replace the hardcoded system prompt with the
                # skill file (.claude/commands/generate-digest.md), which contains
                # tuned format/tag/length rules. Inject dynamic parts (topic
                # instructions, arcs, repetition) after the skill base.
                skill_based_prompt = self._build_claude_p_dialogue_prompt(
                    system_prompt=system_prompt,
                    topic=topic,
                    topic_instructions=instruction.content,
                    story_arc_context=story_arc_context,
                    repetition_instructions=repetition_instructions,
                    digest_date=digest_date,
                    speaker_1_name=speaker_1_name,
                    speaker_2_name=speaker_2_name,
                    num_episodes=len(transcripts),
                )
                script_content = self._call_claude_p(skill_based_prompt, user_prompt)
            else:
                script_content = self._call_llm(system_prompt, user_prompt)

            char_count = len(script_content)

            # Validate and fix dialogue format (v1.96 - enforce SPEAKER_1: format)
            script_content, fixed = self._validate_and_fix_dialogue_format(script_content)
            if fixed:
                logger.warning(f"Auto-corrected dialogue format issues in generated script")
                char_count = len(script_content)  # Update char count after fixes

            # Apply anti-AI writing cleanup (v3.22 - mechanical fixes for patterns LLMs resist)
            script_content = self._apply_anti_ai_cleanup(script_content)
            char_count = len(script_content)

            # Validate character count
            if char_count < 22000:
                logger.warning(f"Dialogue script is shorter than target: {char_count} < 22,000 characters")
            elif char_count > 35000:
                logger.warning(f"Dialogue script exceeds target: {char_count} > 35,000 characters")

            provider = f"OpenAI fallback ({self.OPENAI_FALLBACK_MODEL})" if used_fallback else self.ai_model
            logger.info(f"Generated dialogue script for {topic}: {char_count} characters from {len(episodes)} episodes (via {provider})")
            return script_content, char_count

        except Exception as e:
            logger.error(f"{self.ai_model} error for dialogue script {topic}: {e}")
            raise ScriptGenerationError(f"Failed to generate dialogue script with {self.ai_model}: {e}")

    def _validate_and_fix_dialogue_format(self, script: str) -> Tuple[str, bool]:
        """
        Validate and auto-correct dialogue format issues.

        Fixes common format errors:
        - SPEAKER_1 [tag] text → SPEAKER_1: [tag] text (missing colon)
        - SPEAKER_1 [tag]: text → SPEAKER_1: [tag] text (colon after tag)
        - Host 1: text → SPEAKER_1: text (wrong speaker name)

        Args:
            script: Generated dialogue script

        Returns:
            Tuple of (corrected_script, was_fixed)
        """
        import re

        fixed = False
        original_script = script

        # Fix 1: SPEAKER_1 [tag] text → SPEAKER_1: [tag] text (add missing colon)
        pattern1 = re.compile(r'^(SPEAKER_[12])\s+(\[)', re.MULTILINE)
        if pattern1.search(script):
            script = pattern1.sub(r'\1: \2', script)
            fixed = True
            logger.warning("Fixed missing colons after speaker labels")

        # Fix 2: SPEAKER_1 [tag]: text → SPEAKER_1: [tag] text (move colon before tag)
        pattern2 = re.compile(r'^(SPEAKER_[12])\s+(\[[^\]]+\]):\s+', re.MULTILINE)
        if pattern2.search(script):
            script = pattern2.sub(r'\1: \2 ', script)
            fixed = True
            logger.warning("Fixed colon position (moved before audio tags)")

        # Fix 3: Host 1: / Host 2: → SPEAKER_1: / SPEAKER_2:
        pattern3 = re.compile(r'^Host\s+([12]):\s+', re.MULTILINE)
        if pattern3.search(script):
            script = pattern3.sub(r'SPEAKER_\1: ', script)
            fixed = True
            logger.warning("Fixed 'Host N:' to 'SPEAKER_N:'")

        # Fix 4: Named hosts (Maya:, Jules:, etc.) → SPEAKER_1: / SPEAKER_2:
        # This is trickier - we need to track which name maps to which speaker
        pattern4 = re.compile(r'^([A-Z][a-z]+):\s+', re.MULTILINE)
        named_matches = pattern4.findall(script)
        if named_matches and 'SPEAKER_' not in script:
            # Map unique names to SPEAKER_1/SPEAKER_2
            unique_names = []
            for name in named_matches:
                if name not in unique_names and name not in ['SPEAKER_1', 'SPEAKER_2']:
                    unique_names.append(name)

            if len(unique_names) == 2:
                # Replace first name with SPEAKER_1, second with SPEAKER_2
                script = re.sub(rf'^{unique_names[0]}:\s+', 'SPEAKER_1: ', script, flags=re.MULTILINE)
                script = re.sub(rf'^{unique_names[1]}:\s+', 'SPEAKER_2: ', script, flags=re.MULTILINE)
                fixed = True
                logger.warning(f"Fixed named speakers '{unique_names[0]}'/'{unique_names[1]}' to SPEAKER_1/SPEAKER_2")

        # Validate: Check if script now has proper SPEAKER_1: and SPEAKER_2: labels
        if 'SPEAKER_1:' in script and 'SPEAKER_2:' in script:
            logger.debug("Dialogue format validated successfully")
        else:
            logger.error(f"Dialogue script still missing proper SPEAKER labels after fixes. Contains SPEAKER_1: {('SPEAKER_1:' in script)}, SPEAKER_2: {('SPEAKER_2:' in script)}")

        return script, fixed

    def _apply_anti_ai_cleanup(self, script: str) -> str:
        """Post-generation cleanup: mechanical contraction fixes + LLM structural variety pass.

        Two phases:
        1. Mechanical: contraction enforcement (always safe, always correct)
        2. LLM pass: rewrite sentences with repetitive structure, monotonous rhythm,
           or AI-tell patterns. Focuses on how the script SOUNDS, not visual punctuation.
        """
        import re

        original_len = len(script)

        # Phase 1: LLM structural variety pass (rewrites sentences for varied rhythm)
        script = self._run_structural_variety_pass(script)

        # Phase 2: Mechanical contraction enforcement AFTER LLM pass
        # (LLM may re-introduce formal forms during rewriting)
        contractions = [
            (r'\bis not\b', "isn't"),
            (r'\bare not\b', "aren't"),
            (r'\bdo not\b', "don't"),
            (r'\bdoes not\b', "doesn't"),
            (r'\bdid not\b', "didn't"),
            (r'\bcannot\b', "can't"),
            (r'\bwill not\b', "won't"),
            (r'\bwould not\b', "wouldn't"),
            (r'\bcould not\b', "couldn't"),
            (r'\bshould not\b', "shouldn't"),
        ]
        contraction_fixes = 0
        for pattern, replacement in contractions:
            count = len(re.findall(pattern, script, re.IGNORECASE))
            if count > 0:
                script = re.sub(pattern, replacement, script, flags=re.IGNORECASE)
                contraction_fixes += count

        if contraction_fixes > 0:
            logger.info(f"Anti-AI cleanup: fixed {contraction_fixes} missing contractions")

        logger.info(f"Anti-AI cleanup complete: {original_len} -> {len(script)} chars")
        return script

    def _run_structural_variety_pass(self, script: str) -> str:
        """Use a fast, cheap LLM to rewrite sentences with repetitive structure.

        Focuses on what matters for audio:
        - Sentence structure monotony (same clause patterns repeated)
        - Both speakers sounding identical in rhythm and construction
        - Formulaic transitions and reactions
        - Banned AI-tell phrases that need sentence-level rewriting, not word substitution

        Uses claude -p (free via Max subscription) for the rewrite pass.
        """
        system_prompt = """You are a script editor for a two-host podcast. Your job is to improve how the script SOUNDS when read aloud by fixing structural monotony and AI-tell patterns.

RULES:
1. Preserve ALL facts, names, numbers, dates, speaker labels (SPEAKER_1:/SPEAKER_2:), and audio tags ([excited], [thoughtful], etc.) EXACTLY.
2. Preserve the overall structure — same number of speaker turns, same topic order, same meaning.
3. DO NOT add new content, remove content, or change who says what.
4. DO NOT add commentary, headers, or notes — output ONLY the revised script.

WHAT TO FIX:
- Sentences that all follow the same structure (subject-verb-parenthetical-clause, repeated). Vary the construction: some simple, some compound, some starting with a dependent clause, some very short.
- Both speakers using identical sentence patterns. SPEAKER_1 should use shorter, punchier constructions. SPEAKER_2 should use longer, more technical ones. They should NOT sound interchangeable.
- Formulaic phrases: rewrite (don't just delete) sentences containing "genuinely" (as intensifier), "the framing," "throughline/through-line," "connect the threads," "what surprised you/us," "worth noting/watching/flagging," "deep dive," "break that down," "both things can be true," "doing a lot of work in that sentence."
- "That's a [adjective] [noun]" as standalone summary sentences — rewrite as natural reactions.
- Manufactured disagreements: rewrite any "I want to push back" / "I disagree" / "I see it differently" — the hosts are curators presenting source material, not pundits with their own positions. If there's tension, it should come from contrasting source perspectives, attributed to the original speakers.
- Performed uncertainty: rewrite "I honestly don't know" / "I haven't figured out what I think" — the hosts don't have opinions to be uncertain about.
- Sentences that all use em dashes for subordinate clauses — restructure some to use different constructions (appositives, parentheticals, separate sentences, semicolons).

WHAT NOT TO TOUCH:
- Sentences that already sound natural and varied — leave them alone.
- Technical terms, proper nouns, data points, quotes.
- Audio tags and speaker labels — preserve exactly.
- The overall length — stay within 5% of the original character count.

DO NOT INTRODUCE:
- Do NOT add em dashes that weren't there. If you're restructuring a sentence, use commas, semicolons, colons, or separate sentences — not em dashes.
- Do NOT use these phrases in your rewrites: "genuinely," "the framing," "throughline," "deep dive," "break that down," "worth noting," "both things can be true," "I want to push back," "I honestly don't know."
- Do NOT add manufactured disagreements between hosts. They are curators, not pundits.
- Do NOT expand contractions. Keep "isn't," "don't," "can't" as contractions."""

        user_prompt = f"""Revise this podcast script for structural variety. Fix monotonous sentence patterns and AI-tell phrases. Preserve all content, speaker labels, and audio tags exactly.

{script}"""

        # v3.29: skip the structural variety pass entirely if claude -p is broken.
        # Without this guard, a hung claude -p eats 10 minutes per cron run.
        try:
            from src.utils.claude_p_health import is_claude_p_healthy
            if not is_claude_p_healthy():
                logger.warning("Structural variety pass: claude -p unhealthy, keeping original script")
                return script
        except Exception:
            pass

        try:
            logger.info(f"Running structural variety pass via claude -p ({len(script)} chars)")
            revised = self._call_claude_p(system_prompt, user_prompt, timeout=360).strip()

            # Validate the result
            if not revised or len(revised) < len(script) * 0.5:
                logger.warning(f"Structural variety pass returned too-short result ({len(revised)} chars), keeping original")
                return script

            if 'SPEAKER_1:' not in revised or 'SPEAKER_2:' not in revised:
                logger.warning("Structural variety pass broke speaker labels, keeping original")
                return script

            # Check it didn't explode in length
            if len(revised) > len(script) * 1.15:
                logger.warning(f"Structural variety pass expanded script too much ({len(revised)} vs {len(script)}), keeping original")
                return script

            logger.info(f"Structural variety pass complete: {len(script)} -> {len(revised)} chars ({len(revised) - len(script):+d})")
            return revised

        except Exception as e:
            logger.warning(f"Structural variety pass failed ({e}), keeping original script")
            # Note: we intentionally do NOT call mark_unhealthy() here.
            # The variety pass is optional polish — its timeout should never
            # poison critical downstream features (dedup, reconciler, scrubber).
            return script

    def _generate_narrative_script(self, topic: str, episodes: List[Episode],
                                   digest_date: date, instruction: TopicInstruction,
                                   recently_covered_arcs: Optional[List[str]] = None) -> Tuple[str, int]:
        """
        Generate narrative-style script for single-voice delivery (Turbo v2.5).
        Target: 10,000-15,000 characters with TTS optimization.

        Args:
            topic: Topic name
            episodes: List of episodes to include
            digest_date: Date of digest
            instruction: Topic configuration
            recently_covered_arcs: Optional list of arc names recently covered.
                If provided, prompts include instructions to focus on NEW content.

        Returns:
            Tuple of (script_content, character_count)
        """
        # Prepare episode transcripts
        transcripts = []
        total_ads_filtered = 0
        for episode in episodes:
            if not episode.transcript_content or not episode.transcript_content.strip():
                logger.error(f"No transcript content in database for episode: {episode.title}")
                raise ScriptGenerationError(f"Episode {episode.title} has no transcript content in database")

            # Apply ad filtering if available
            transcript_content = episode.transcript_content
            if self.ad_filter:
                transcript_content, detected_ads = self.ad_filter.filter_transcript(transcript_content)
                if detected_ads:
                    total_ads_filtered += len(detected_ads)
                    logger.info(f"Filtered {len(detected_ads)} ad types from '{episode.title}': {', '.join(detected_ads)}")

            transcripts.append({
                'title': episode.title,
                'published_date': episode.published_date.strftime('%Y-%m-%d'),
                'transcript': transcript_content,
                'score': episode.scores.get(topic, 0.0) if episode.scores else 0.0
            })

        if total_ads_filtered > 0:
            logger.info(f"Total ad filtering: {total_ads_filtered} ad types removed from {len(episodes)} episodes")

        # Retrieve active story arcs FIRST with TTS-safe names (need length for token budget)
        story_arc_context = self._get_recent_story_arc_context(
            topic,
            episodes=episodes,  # Ground arcs to episode content
            for_narrative=True  # Include TTS-safe arc names
        )

        # Build repetition avoidance instructions if arcs were recently covered
        repetition_instructions = ""
        if recently_covered_arcs:
            repetition_instructions = self._build_repetition_avoidance_instructions(recently_covered_arcs, topic=topic)
            logger.info(f"Adding repetition avoidance for {len(recently_covered_arcs)} recently covered arcs")

        # Calculate transcript limit with arc context reserved
        arc_context_length = len(story_arc_context) + len(repetition_instructions)
        transcript_limit = self._calculate_transcript_limit(len(transcripts), arc_context_length)

        # Generate narrative script with TTS optimization for ElevenLabs Turbo v2.5
        system_prompt = f"""You are a professional podcast script writer creating a narrative digest for the topic "{topic}".

TOPIC INSTRUCTIONS:
{instruction.content}
{story_arc_context}
{repetition_instructions}

**CRITICAL - STORY ARC GROUNDING:**
Only reference story arcs that have supporting evidence in the episode transcripts provided below.
Do not invent or assume developments not present in the transcript content.
When referencing arc names, use the "Spoken" form if provided for TTS compatibility.

TTS OPTIMIZATION REQUIREMENTS (CRITICAL):
Your script will be converted to audio using ElevenLabs TTS. Follow these rules EXACTLY:

1. TEXT NORMALIZATION:
   - Write ALL numbers in full spoken form (e.g., "twenty twenty-four" not "2024")
   - Expand ALL abbreviations (e.g., "January" not "Jan", "Doctor" not "Dr.")
   - Convert ALL symbols to words (e.g., "and" not "&", "dollars" not "$")
   - Spell out ALL monetary values (e.g., "one hundred dollars" not "$100")
   - Write ALL percentages in full (e.g., "twenty-five percent" not "25%")
   - Expand ALL measurements (e.g., "one hundred kilometers" not "100km")

2. DATES AND TIMES:
   - Full expansion: "January second, twenty twenty-four" not "01/02/2024"
   - Years: "twenty twenty-four" or "two thousand twenty-four"
   - Times: "two thirty PM" not "14:30"

3. ABBREVIATIONS TO AVOID:
   - "Dr." → "Doctor"
   - "Ave." → "Avenue"
   - "etc." → "etcetera" or rephrase
   - "e.g." → "for example"
   - "i.e." → "that is"
   - "CEO" → "C E O" or "Chief Executive Officer"
   - "AI" → "A I" or "artificial intelligence"

4. NARRATIVE EMOTION STYLE:
   - Use dialogue tags for emotion: "she said excitedly" instead of emotion markers
   - Add emotional context naturally: "He paused, taking a deep breath before continuing."
   - Use punctuation for expression: exclamation marks (!), ellipses (...), questions (?)
   - Examples:
     * "The researcher explained thoughtfully, we need to consider multiple perspectives."
     * "She said excitedly, this is the most important discovery of the decade."

5. SCRIPT STRUCTURE:
   - Target 10,000-15,000 characters (measured in characters, not words)
   - Write in natural, conversational speech patterns
   - Use clear paragraph breaks for topic transitions
   - Maintain engaging, audio-friendly tone
   - Include episode titles and dates when relevant
   - Focus on the most important insights and developments

Date: {digest_date.strftime('%B %d, %Y')}
Topic: {topic}
Episodes: {len(transcripts)}"""

        user_prompt = f"""Create a narrative digest script from these {len(transcripts)} episode(s):

IMPORTANT - TRANSCRIPT AVAILABILITY:
You have COMPLETE access to ALL {len(transcripts)} episode transcripts provided below. Each transcript contains the full content needed to discuss that episode in detail. DO NOT claim you don't have access to any transcript, as all transcripts are fully provided. If a transcript seems shorter, it's because the episode itself was shorter or content was truncated for length - the key insights are present.

"""

        for i, transcript_data in enumerate(transcripts, 1):
            user_prompt += f"""Episode {i}: "{transcript_data['title']}" (Published: {transcript_data['published_date']}, Relevance Score: {transcript_data['score']:.2f})

Transcript:
{transcript_data['transcript'][:transcript_limit]}

---

"""

        user_prompt += f"""Generate a TTS-optimized narrative script following ALL the text normalization rules above. Target 10,000-15,000 characters. Remember: expand ALL numbers, dates, and abbreviations to their full spoken form.

REMINDER: You have full transcripts for ALL {len(transcripts)} episodes above. Discuss each episode's content directly based on the transcript provided - do not claim any transcripts are missing or unavailable."""

        try:
            script_content = self._call_llm(system_prompt, user_prompt)
            char_count = len(script_content)

            # Validate character count
            if char_count < 10000:
                logger.warning(f"Narrative script is shorter than target: {char_count} < 10,000 characters")
            elif char_count > 15000:
                logger.warning(f"Narrative script exceeds target: {char_count} > 15,000 characters")

            logger.info(f"Generated narrative script for {topic}: {char_count} characters from {len(episodes)} episodes")
            return script_content, char_count

        except Exception as e:
            logger.error(f"{self.ai_model} error for narrative script {topic}: {e}")
            raise ScriptGenerationError(f"Failed to generate narrative script with {self.ai_model}: {e}")

    def _run_dedup_pass_with_retry(
        self,
        topic: str,
        draft_script: str,
        episodes: List[Episode],
        digest_date: date,
        recently_covered_arcs: Optional[List[str]],
    ) -> Optional[Dict]:
        """Dynamic dedup + episode expansion loop (v3.27+).

        1. Run dedup on the initial draft.
        2. If the result is at or above `target_chars_floor`, done.
        3. Otherwise, pull ONE more scored-but-unused episode, scrub
           saturated-topic content from all episode transcripts, regenerate
           the draft from scratch, and re-run dedup.
        4. Repeat until the floor is hit, no more episodes remain, or
           `max_iterations` exceeded.

        Returns a dict with {script_content, word_count, episodes, predupe_content}
        or None if the dedup pass is disabled.
        """
        if not self.web_config:
            return None

        try:
            from src.config.web_config import SettingsKeys
            enabled = self.web_config.get_setting(
                SettingsKeys.Dedup.CATEGORY,
                SettingsKeys.Dedup.ENABLED,
                True,
            )
            if not enabled:
                logger.info("Dedup pass disabled via web_settings")
                return None

            lookback = int(self.web_config.get_setting(
                SettingsKeys.Dedup.CATEGORY,
                SettingsKeys.Dedup.LOOKBACK_DIGESTS,
                8,
            ))
            target_floor = int(self.web_config.get_setting(
                SettingsKeys.Dedup.CATEGORY,
                SettingsKeys.Dedup.TARGET_CHARS_FLOOR,
                20000,
            ))
            max_expansion = int(self.web_config.get_setting(
                SettingsKeys.Dedup.CATEGORY,
                SettingsKeys.Dedup.MAX_EXPANSION_EPISODES,
                5,
            ))
            max_iterations = int(self.web_config.get_setting(
                SettingsKeys.Dedup.CATEGORY,
                SettingsKeys.Dedup.MAX_ITERATIONS,
                5,
            ))
            scrub_on_regen = bool(self.web_config.get_setting(
                SettingsKeys.Dedup.CATEGORY,
                SettingsKeys.Dedup.SCRUB_TRANSCRIPTS_ON_REGEN,
                True,
            ))
        except Exception as e:
            logger.warning(f"Dedup pass config read failed, skipping: {e}")
            return None

        try:
            from src.generation.dedup_pass import run_dedup_pass
        except Exception as e:
            logger.warning(f"Dedup pass module import failed, skipping: {e}")
            return None

        # Iteration 0 state
        predupe_content = draft_script
        current_script = draft_script
        current_episodes = list(episodes)
        starting_count = len(episodes)

        # Collect saturated topic names once for scrub + potentially log
        saturated_topic_names = list(recently_covered_arcs or [])

        for iteration in range(max_iterations):
            # Run dedup against the current draft
            result = run_dedup_pass(
                draft_script=current_script,
                topic=topic,
                lookback=lookback,
            )

            if result.skipped:
                logger.info(
                    f"Dedup iteration {iteration}: skipped ({result.skip_reason}); "
                    f"accepting current draft"
                )
                return {
                    "script_content": current_script,
                    "word_count": len(current_script.split()),
                    "episodes": current_episodes,
                    "predupe_content": predupe_content,
                }

            deduped_script = result.rewritten_script
            chars_after = result.chars_after

            logger.info(
                f"Dedup iteration {iteration}: "
                f"{result.chars_before} -> {chars_after} chars, "
                f"floor={target_floor}, episodes={len(current_episodes)}"
            )

            # Did we hit the floor?
            if chars_after >= target_floor:
                logger.info(f"Dedup iteration {iteration}: target floor reached")
                return {
                    "script_content": deduped_script,
                    "word_count": len(deduped_script.split()),
                    "episodes": current_episodes,
                    "predupe_content": predupe_content,
                }

            # Can we expand further?
            expansions_used = len(current_episodes) - starting_count
            if expansions_used >= max_expansion:
                logger.info(
                    f"Dedup iteration {iteration}: expansion cap reached "
                    f"({expansions_used}/{max_expansion}); accepting shorter script"
                )
                return {
                    "script_content": deduped_script,
                    "word_count": len(deduped_script.split()),
                    "episodes": current_episodes,
                    "predupe_content": predupe_content,
                }

            existing_ids = {ep.id for ep in current_episodes if ep.id is not None}
            extra_episodes = self._get_extra_scored_episodes(
                topic=topic,
                exclude_ids=existing_ids,
                limit=1,
            )
            if not extra_episodes:
                logger.info(
                    f"Dedup iteration {iteration}: no more scored episodes available "
                    f"for '{topic}'; accepting shorter script ({chars_after} chars)"
                )
                return {
                    "script_content": deduped_script,
                    "word_count": len(deduped_script.split()),
                    "episodes": current_episodes,
                    "predupe_content": predupe_content,
                }

            expanded = list(current_episodes) + list(extra_episodes)
            logger.info(
                f"Dedup iteration {iteration}: pulled 1 extra episode "
                f"('{extra_episodes[0].title[:60]}'), total now {len(expanded)}"
            )

            # Scrub saturated content from ALL transcripts so the next
            # generation pass doesn't reintroduce what we already cut.
            gen_episodes = expanded
            if scrub_on_regen and saturated_topic_names:
                try:
                    from src.generation.transcript_scrubber import scrub_episodes
                    gen_episodes = scrub_episodes(
                        expanded,
                        saturated_topic_names,
                    )
                except Exception as e:
                    logger.warning(
                        f"Transcript scrub failed ({e}); regenerating with original transcripts"
                    )
                    gen_episodes = expanded

            # Regenerate from scratch with the expanded (and possibly scrubbed) set
            try:
                new_script, _new_word_count = self.generate_script(
                    topic,
                    gen_episodes,
                    digest_date,
                    recently_covered_arcs=saturated_topic_names,
                )
            except Exception as e:
                logger.warning(
                    f"Dedup iteration {iteration}: regeneration failed ({e}); "
                    f"accepting current deduped draft"
                )
                return {
                    "script_content": deduped_script,
                    "word_count": len(deduped_script.split()),
                    "episodes": current_episodes,
                    "predupe_content": predupe_content,
                }

            # Advance loop state. Note: current_episodes uses the UNSCRUBBED
            # episode list for DB linking — we only scrub the copies we feed
            # to the generator.
            predupe_content = new_script
            current_script = new_script
            current_episodes = expanded

        # Fell out of the loop at max_iterations — run one final dedup and return
        logger.info(
            f"Dedup: hit max_iterations ({max_iterations}); finalizing"
        )
        final_result = run_dedup_pass(
            draft_script=current_script,
            topic=topic,
            lookback=lookback,
        )
        final_script = (
            final_result.rewritten_script
            if not final_result.skipped
            else current_script
        )
        return {
            "script_content": final_script,
            "word_count": len(final_script.split()),
            "episodes": current_episodes,
            "predupe_content": predupe_content,
        }

    def _get_extra_scored_episodes(
        self,
        topic: str,
        exclude_ids: set,
        limit: int,
    ) -> List[Episode]:
        """Greedy by score: pull up to `limit` scored-but-undigested episodes
        for this topic that aren't already in the current digest.
        """
        try:
            pool = self.episode_repo.get_scored_episodes_for_topic(
                topic=topic,
                min_score=self.score_threshold,
            )
        except Exception as e:
            logger.warning(f"Failed to fetch extra scored episodes: {e}")
            return []

        # Exclude already-included and ensure transcript is present
        MIN_TRANSCRIPT_CHARS = 1000
        candidates = [
            ep for ep in pool
            if ep.id not in exclude_ids
            and ep.transcript_content
            and len(ep.transcript_content) >= MIN_TRANSCRIPT_CHARS
        ]
        # Sort by score desc
        candidates.sort(
            key=lambda ep: ep.scores.get(topic, 0.0) if ep.scores else 0.0,
            reverse=True,
        )
        return candidates[:limit]

    def get_qualifying_episodes(self, topic: str, start_date: date = None,
                              end_date: date = None, max_episodes: int = None) -> List[Episode]:
        """
        Get episodes that qualify for digest generation.

        Returns only:
        - Episodes with score >= threshold for the topic
        - Episodes that haven't been digested yet (status == 'scored')
        - Limited to max_episodes per topic to maintain digest quality
        """
        all_qualifying = self.episode_repo.get_scored_episodes_for_topic(
            topic=topic,
            min_score=self.score_threshold,
            start_date=start_date,
            end_date=end_date
        )

        # Filter out episodes with transcripts too short for meaningful digest content
        MIN_DIGEST_TRANSCRIPT_CHARS = 1000
        before_count = len(all_qualifying)
        all_qualifying = [
            ep for ep in all_qualifying
            if ep.transcript_content and len(ep.transcript_content) >= MIN_DIGEST_TRANSCRIPT_CHARS
        ]
        filtered_count = before_count - len(all_qualifying)
        if filtered_count > 0:
            logger.warning(f"Filtered out {filtered_count} episodes with transcripts shorter than {MIN_DIGEST_TRANSCRIPT_CHARS} chars")

        # v3.28: Apply feed priority ordering when enabled. Feeds the user
        # ranked higher in the Feeds UI get first pick when selecting the
        # episodes to include in a digest. Ties broken by topic score desc.
        feed_priorities = self._get_feed_priorities_if_enabled()
        if feed_priorities is not None:
            def sort_key(ep: Episode):
                prio = feed_priorities.get(ep.feed_id, 999999)
                score = ep.scores.get(topic, 0.0) if ep.scores else 0.0
                # priority ASC (lower=better), score DESC (higher=better)
                return (prio, -score)
            all_qualifying = sorted(all_qualifying, key=sort_key)
        else:
            # Default: sort by score descending (original behavior)
            all_qualifying = sorted(
                all_qualifying,
                key=lambda ep: ep.scores.get(topic, 0.0) if ep.scores else 0.0,
                reverse=True,
            )

        # Determine cap
        cap = max_episodes if isinstance(max_episodes, int) and max_episodes > 0 else self.max_episodes_per_digest
        if cap and len(all_qualifying) > cap:
            logger.info(f"Limiting {topic} episodes from {len(all_qualifying)} to {cap} (saving {len(all_qualifying) - cap} for future digests)")
            return all_qualifying[:cap]

        return all_qualifying

    def _get_feed_priorities_if_enabled(self) -> Optional[Dict[int, int]]:
        """Return {feed_id: priority} if feed priority ordering is enabled, else None.

        v3.28+: Gated on web_settings.feed_priority.enabled (default True).
        """
        if not self.web_config:
            return None
        try:
            from src.config.web_config import SettingsKeys
            enabled = self.web_config.get_setting(
                SettingsKeys.FeedPriority.CATEGORY,
                SettingsKeys.FeedPriority.ENABLED,
                True,
            )
            if not enabled:
                return None
        except Exception:
            return None

        try:
            from src.database.models import get_database_manager
            from src.database.sqlalchemy_models import Feed as FeedModel
            db = get_database_manager()
            with db.get_session() as session:
                rows = session.query(FeedModel.id, FeedModel.priority).all()
                return {fid: (p if p is not None else 999999) for fid, p in rows}
        except Exception as e:
            logger.debug(f"Feed priority lookup failed, falling back to score-only sort: {e}")
            return None

    def _check_topic_repetition(self, episodes: List[Episode], topic: str) -> Tuple[bool, str, List[str]]:
        """
        Check if the digest would have significant overlap with recent coverage.

        Compares active story arcs against arcs included in digests from
        the last 3 days. If >20% of arcs were recently covered, returns
        info to help the prompt focus on NEW developments only.

        Args:
            episodes: List of episodes to check
            topic: Topic name

        Returns:
            Tuple of (has_significant_overlap, message, recently_covered_arc_names)
            - has_significant_overlap: True if >50% of arcs were recently covered
            - message: Human-readable description of overlap
            - recently_covered_arc_names: List of arc names that were recently covered
        """
        if not self.story_arc_repo:
            return False, "", []

        try:
            # Get all active arcs for this topic (last 14 days)
            active_arcs = self.story_arc_repo.get_active_story_arcs(topic, days=14)
            if not active_arcs:
                return False, "No active story arcs found", []

            # Get arcs that were included in digests in the last 3 days
            recently_included = self.story_arc_repo.get_recently_included_arcs(topic, days=3)
            recently_included_names = {arc['arc_name'] for arc in recently_included}

            if not recently_included_names:
                return False, "No recently covered arcs", []

            # Calculate overlap
            active_arc_names = {arc['arc_name'] for arc in active_arcs}
            overlap = active_arc_names & recently_included_names
            overlap_count = len(overlap)
            total_active = len(active_arc_names)

            if total_active == 0:
                return False, "No active arcs to compare", []

            overlap_pct = (overlap_count / total_active) * 100

            # Check if significant overlap (>20% - lowered from 50% for better repetition avoidance)
            has_significant_overlap = overlap_pct > 20

            if has_significant_overlap:
                message = (
                    f"{overlap_count}/{total_active} arcs ({overlap_pct:.0f}%) were covered "
                    f"in the last 3 days. Digest will focus on NEW developments only."
                )
                logger.info(f"Story arc overlap detected for {topic}: {message}")
            else:
                message = f"Low overlap: {overlap_count}/{total_active} arcs ({overlap_pct:.0f}%) recently covered"

            return has_significant_overlap, message, list(overlap)

        except Exception as e:
            logger.warning(f"Failed to check topic repetition for {topic}: {e}")
            return False, f"Error checking repetition: {e}", []

    def generate_script(self, topic: str, episodes: List[Episode],
                       digest_date: date,
                       recently_covered_arcs: Optional[List[str]] = None) -> Tuple[str, int]:
        """
        Generate digest script for topic using GPT-5.
        Routes to dialogue or narrative mode based on topic configuration.

        Args:
            topic: Topic name
            episodes: List of episodes to include
            digest_date: Date of the digest
            recently_covered_arcs: Optional list of arc names that were covered
                in recent digests. If provided, prompts will include instructions
                to focus on NEW developments and avoid repeating old content.

        Returns (script_content, count) where count is:
        - character_count for dialogue mode
        - word_count for narrative mode (backward compatibility)
        """
        if topic not in self.topic_instructions:
            raise ScriptGenerationError(f"No instructions found for topic: {topic}")

        instruction = self.topic_instructions[topic]

        # Handle no content case
        if not episodes:
            return self._generate_no_content_script(topic, digest_date)

        # Check if dialogue mode is enabled for this topic
        is_dialogue = self._is_dialogue_mode(topic)

        if is_dialogue:
            logger.info(f"Generating DIALOGUE script for {topic} (multi-voice with audio tags)")
            return self._generate_dialogue_script(topic, episodes, digest_date, instruction, recently_covered_arcs)
        else:
            logger.info(f"Generating NARRATIVE script for {topic} (single-voice TTS-optimized)")
            return self._generate_narrative_script(topic, episodes, digest_date, instruction, recently_covered_arcs)
    
    def _generate_no_content_script(self, topic: str, digest_date: date) -> Tuple[str, int]:
        """Generate script for days with no qualifying content"""
        script = f"""# {topic} Daily Digest - {digest_date.strftime('%B %d, %Y')}

Hello and welcome to your {topic} digest for {digest_date.strftime('%B %d, %Y')}.

Today, we don't have any new episodes that meet our quality threshold for this topic. This sometimes happens, and it's completely normal in the world of podcast content.

Instead of delivering lower-quality content, we prefer to wait for episodes that truly add value to your understanding of {topic.lower()}.

We'll be back tomorrow with fresh insights and analysis. In the meantime, you might want to check out our other topic digests for today, or revisit some of our recent high-quality episodes.

Thank you for your understanding, and we'll see you tomorrow!

---
*This digest was automatically generated when no episodes met our quality threshold of {self.score_threshold:.0%} relevance.*"""
        
        word_count = len(script.split())
        logger.info(f"Generated no-content script for {topic}: {word_count} words")
        return script, word_count
    
    def save_script(self, topic: str, digest_date: date, content: str, word_count: int, digest_timestamp: datetime = None) -> str:
        """Save script to file and return file path"""
        if digest_timestamp is None:
            digest_timestamp = datetime.now(UTC)

        timestamp = digest_timestamp.strftime('%Y%m%d_%H%M%S')
        filename = f"{topic.replace(' ', '_')}_{digest_date.strftime('%Y%m%d')}_{timestamp}.md"
        script_path = self.scripts_dir / filename

        try:
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"Saved script to: {script_path}")
            return str(script_path)

        except Exception as e:
            logger.error(f"Failed to save script to {script_path}: {e}")
            raise ScriptGenerationError(f"Failed to save script: {e}")
    
    def create_digest(self, topic: str, digest_date: date,
                     start_date: date = None, end_date: date = None) -> Optional[Digest]:
        """
        Create complete digest: find episodes, generate script, save to database.
        Returns created Digest object, or None if insufficient episodes.
        Multiple digests per topic per day are allowed (with unique timestamps).
        """
        logger.info(f"Creating digest for {topic} on {digest_date}")

        # Find qualifying episodes FIRST - only undigested scored episodes
        # This allows multiple digests per day when new episodes are scored
        episodes = self.get_qualifying_episodes(topic, start_date, end_date)
        logger.info(f"Found {len(episodes)} qualifying undigested episodes for {topic}")

        # If no new episodes, check if we already have a digest for today
        # Only return existing digest if there are NO new episodes to process
        if len(episodes) == 0:
            existing_digest = self.digest_repo.get_by_topic_date(topic, digest_date)
            if existing_digest and existing_digest.script_content:
                logger.info(f"No new episodes and digest already exists for {topic} on {digest_date} (ID: {existing_digest.id}), returning existing digest")
                return existing_digest
            else:
                logger.info(f"No qualifying undigested episodes found for {topic}, generating no-content digest")
                episodes = []  # Will generate no-content script
        elif len(episodes) < self.min_episodes_per_digest:
            # Not enough episodes to meet minimum threshold
            logger.info(f"Insufficient episodes for {topic} digest: {len(episodes)} < {self.min_episodes_per_digest} (minimum required). Skipping digest creation.")

            # Check if existing digest exists - return it if available
            existing_digest = self.digest_repo.get_by_topic_date(topic, digest_date)
            if existing_digest and existing_digest.script_content:
                logger.info(f"Returning existing digest for {topic} on {digest_date} (ID: {existing_digest.id})")
                return existing_digest
            else:
                logger.info(f"No existing digest found for {topic} - skipping digest creation")
                return None
        else:
            logger.info(f"Including {len(episodes)} undigested episodes in {topic} digest (>= min {self.min_episodes_per_digest})")
            # Episodes will be used as-is, capped at max_episodes_per_digest (done by get_qualifying_episodes)

            # Check if a digest already exists for this topic/date (for logging purposes)
            existing_digest = self.digest_repo.get_by_topic_date(topic, digest_date)
            if existing_digest:
                logger.info(f"Creating NEW digest for {topic} on {digest_date} with unique timestamp (existing digest ID: {existing_digest.id} will remain)")

        # Check for story arc overlap with recent digests
        # If significant overlap, we'll add "update framing" to focus on NEW content only
        has_overlap, overlap_msg, recently_covered_arcs = self._check_topic_repetition(episodes, topic)
        if has_overlap:
            logger.info(f"Story arc overlap for {topic}: {overlap_msg}")

        # v3.34: Pre-generation transcript dedup — strip repeated content from
        # transcripts BEFORE the script generator sees them. This replaces the
        # post-generation dedup pass which couldn't fix content the LLM never
        # generated in the first place.
        original_episodes = list(episodes)
        try:
            from src.generation.transcript_dedup import dedup_episode_batch
            from src.database.sqlalchemy_models import Digest as DigestModel
            from src.database.models import get_database_manager

            db = get_database_manager()
            with db.get_session() as session:
                # Fetch last 14 digests (~2 weeks) so the dedup pass can detect
                # entities/stories introduced earlier in the news cycle. The
                # 200k char cap inside dedup_transcript trims this to roughly
                # the most recent 6-7 digests.
                prior_digests = (
                    session.query(DigestModel)
                    .filter(DigestModel.topic == topic, DigestModel.script_content.isnot(None))
                    .order_by(DigestModel.generated_at.desc())
                    .limit(14)
                    .all()
                )
                prior_scripts = [d.script_content for d in prior_digests]

            if prior_scripts:
                dedup_results, _ = dedup_episode_batch(
                    episodes=episodes,
                    prior_digest_scripts=prior_scripts,
                    timeout_per_episode=300,
                )

                # Replace transcript_content with deduped versions
                for ep, result in zip(episodes, dedup_results):
                    if not result.skipped and result.deduped_transcript:
                        ep.transcript_content = result.deduped_transcript
                        logger.info(
                            f"Pre-gen dedup: '{ep.title[:40]}' "
                            f"{result.original_chars:,} -> {result.deduped_chars:,} chars "
                            f"({result.reduction_pct:.0%} removed)"
                        )

                # Remove episodes with no new content
                episodes = [
                    ep for ep, result in zip(episodes, dedup_results)
                    if result.deduped_chars > 0
                ]
                if len(episodes) < len(original_episodes):
                    logger.info(
                        f"Pre-gen dedup: {len(original_episodes) - len(episodes)} episodes "
                        f"had no new content, {len(episodes)} remaining"
                    )
        except Exception as e:
            logger.warning(f"Pre-gen transcript dedup failed ({e}), using original transcripts")
            episodes = original_episodes

        # Generate script (pass repetition info for update framing if needed)
        script_content, word_count = self.generate_script(
            topic, episodes, digest_date,
            recently_covered_arcs=recently_covered_arcs if has_overlap else None
        )

        # Store original (pre-dedup) transcript content for audit
        predupe_content = script_content

        # Save script to file with timestamp for uniqueness
        digest_timestamp = datetime.now(UTC)
        script_path = self.save_script(topic, digest_date, script_content, word_count, digest_timestamp)

        # Create new digest (each run creates a unique digest with timestamp)
        # Note: episode_ids is deprecated (Issue #10), use digest_episode_links instead
        digest = Digest(
            topic=topic,
            digest_date=digest_date,
            digest_timestamp=digest_timestamp,
            episode_count=len(episodes),
            script_path=script_path,
            script_content=script_content,
            script_content_predupe=predupe_content if predupe_content != script_content else None,
            script_word_count=word_count,
            average_score=sum(ep.scores.get(topic, 0.0) for ep in episodes) / len(episodes) if episodes else 0.0
        )

        digest_id = self.digest_repo.create(digest)
        digest.id = digest_id

        logger.info(f"Created digest {digest_id} for {topic}: {word_count} words, {len(episodes)} episodes")

        if digest.id:
            self._persist_digest_links(digest, topic, episodes)
            self._record_topic_generation(topic, digest_timestamp)

        # Mark episodes as digested now that they're included in a digest
        if episodes:  # Only if we actually used episodes
            logger.info(f"Marking {len(episodes)} episodes as digested")
            self.mark_digest_episodes_as_digested(digest)

        # Mark story arcs that were covered in this digest
        if digest.id and script_content:
            arcs_marked = self.mark_covered_story_arcs(digest.id, topic, script_content)
            if arcs_marked > 0:
                logger.info(f"Marked {arcs_marked} story arcs as included in digest {digest.id}")

        # Delete local script file now that content is safely in database (database-first architecture)
        if script_path and Path(script_path).exists():
            try:
                Path(script_path).unlink()
                logger.info(f"Deleted temporary script file (content in database): {Path(script_path).name}")
            except Exception as e:
                logger.warning(f"Failed to delete script file {script_path}: {e}")

        return digest
    
    def create_daily_digests(self, digest_date: date,
                            start_date: date = None, end_date: date = None) -> List[Digest]:
        """Create digests for all active topics for given date"""
        digests = []

        # Try to create topic-specific digests
        for topic_name in self.topic_instructions:
            try:
                digest = self.create_digest(topic_name, digest_date, start_date, end_date)
                if digest:  # Only append if digest was created (may be None if insufficient episodes)
                    digests.append(digest)
            except Exception as e:
                logger.error(f"Failed to create digest for {topic_name}: {e}")
                continue
        
        # Check if we have any qualifying episodes (non-empty digests)
        qualifying_digests = [d for d in digests if d.episode_count > 0]
        
        if not qualifying_digests:
            logger.info("No qualifying episodes for any topics, attempting general summary")
            try:
                general_digest = self.create_general_summary(digest_date, start_date, end_date)
                if general_digest:
                    digests.append(general_digest)
            except Exception as e:
                logger.error(f"Failed to create general summary: {e}")
        
        logger.info(f"Created {len(digests)} digests for {digest_date}")

        # Episodes are now marked as 'digested' automatically in create_digest()
        return digests

    def _record_topic_generation(self, topic_name: str, generated_at: datetime):
        """Update topic metadata when a digest is generated."""
        if not self.topic_repo:
            return
        instruction = self.topic_instructions.get(topic_name)
        if not instruction or instruction.topic_id is None:
            return
        try:
            self.topic_repo.record_generation(instruction.topic_id, generated_at)
        except Exception as exc:
            logger.debug("Failed to record topic generation for %s: %s", topic_name, exc)

    def _persist_digest_links(self, digest: Digest, topic_name: str, episodes: List[Episode]):
        """Persist digest ↔ episode relationships for UI reporting."""
        if not self.digest_episode_link_repo or not digest.id or not episodes:
            return

        links: List[DigestEpisodeLink] = []
        for position, episode in enumerate(episodes, start=1):
            if episode.id is None:
                continue
            score = None
            if episode.scores and topic_name in episode.scores:
                score = episode.scores.get(topic_name)
            links.append(DigestEpisodeLink(
                digest_id=digest.id,
                episode_id=episode.id,
                topic=topic_name,
                score=score,
                position=position
            ))

        if not links:
            return

        try:
            self.digest_episode_link_repo.replace_links_for_digest(digest.id, links)
        except Exception as exc:
            logger.debug("Failed to persist digest episode links for digest %s: %s", digest.id, exc)
    
    def get_undigested_episodes(self, start_date: date = None,
                               end_date: date = None, limit: int = 5) -> List[Episode]:
        """Get undigested episodes for fallback general summary.

        v3.31: EpisodeRepository.get_undigested_episodes() does not accept
        date filters; the date arguments are accepted here for caller
        compatibility but applied client-side after fetching.
        """
        episodes = self.episode_repo.get_undigested_episodes(limit=limit * 4)
        if start_date:
            episodes = [
                ep for ep in episodes
                if ep.published_date and ep.published_date.date() >= start_date
            ]
        if end_date:
            episodes = [
                ep for ep in episodes
                if ep.published_date and ep.published_date.date() <= end_date
            ]
        return episodes[:limit]
    
    def create_general_summary(self, digest_date: date, 
                              start_date: date = None, end_date: date = None) -> Optional[Digest]:
        """
        Create fallback general summary when no topics have qualifying episodes.
        Selects 1-5 undigested episodes and creates a general digest.
        """
        logger.info(f"Creating general summary for {digest_date}")
        
        # Check if we already have any topic-specific digests for this date
        existing_digests = self.digest_repo.get_by_date(digest_date)
        has_topic_digests = any(d.topic != "General Summary" for d in existing_digests)
        
        if has_topic_digests:
            logger.info("Topic-specific digests exist, skipping general summary")
            return None
        
        # Check if general summary already exists
        existing_general = next((d for d in existing_digests if d.topic == "General Summary"), None)
        if existing_general and existing_general.script_path:
            logger.info("General summary already exists for this date")
            return existing_general
        
        # Get undigested episodes
        episodes = self.get_undigested_episodes(start_date, end_date, limit=5)
        if not episodes:
            logger.info("No undigested episodes available for general summary")
            return None
        
        logger.info(f"Found {len(episodes)} undigested episodes for general summary")
        
        # Generate general summary script
        script_content, word_count = self._generate_general_summary_script(episodes, digest_date)
        
        # Save script to file
        script_path = self.save_script("General_Summary", digest_date, script_content, word_count)
        
        # Mark episodes as digested
        for episode in episodes:
            self.mark_episode_as_digested(episode)
        
        # Create digest in database
        if existing_general:
            # Update existing
            self.digest_repo.update_script(existing_general.id, script_path, word_count)
            existing_general.script_path = script_path
            existing_general.script_word_count = word_count
            return existing_general
        else:
            # Create new digest
            # Note: episode_ids is deprecated (Issue #10), use digest_episode_links instead
            digest = Digest(
                topic="General Summary",
                digest_date=digest_date,
                episode_count=len(episodes),
                script_path=script_path,
                script_word_count=word_count,
                average_score=0.0  # No topic-specific score for general summary
            )

            digest_id = self.digest_repo.create(digest)
            digest.id = digest_id

            # Persist episode links for general summary (Issue #10)
            if digest.id:
                self._persist_digest_links(digest, "General Summary", episodes)

            logger.info(f"Created general summary digest {digest_id}: {word_count} words, {len(episodes)} episodes")
            return digest
    
    def _generate_general_summary_script(self, episodes: List[Episode], 
                                        digest_date: date) -> Tuple[str, int]:
        """Generate a general summary script from undigested episodes"""
        # Prepare episode transcripts
        transcripts = []
        for episode in episodes:
            # Read transcript content from database (REQUIRED - no file fallbacks)
            if not episode.transcript_content or not episode.transcript_content.strip():
                logger.error(f"No transcript content in database for episode: {episode.title}")
                raise ScriptGenerationError(f"Episode {episode.title} has no transcript content in database - system requires database content")

            transcript = episode.transcript_content
            logger.debug(f"Using transcript from database for episode: {episode.title}")

            if transcript:
                transcripts.append({
                    'title': episode.title,
                    'published_date': episode.published_date.strftime('%Y-%m-%d'),
                    'transcript': transcript
                })
        
        if not transcripts:
            # Return basic message if no transcripts available
            script = f"""# General Summary - {digest_date.strftime('%B %d, %Y')}

Hello and welcome to your general podcast digest for {digest_date.strftime('%B %d, %Y')}.

Today we found some interesting podcast episodes that didn't quite reach our specific topic thresholds, but still contain valuable insights worth sharing.

Unfortunately, we encountered some technical issues accessing the episode transcripts. We'll work to resolve this and provide you with better content tomorrow.

Thank you for your patience, and we'll see you tomorrow with fresh insights!

---
*This digest was automatically generated from episodes that didn't meet specific topic thresholds.*"""
            return script, len(script.split())
        
        transcript_limit = min(10000, self._calculate_transcript_limit(len(transcripts)))

        # Generate script using configured AI model
        system_prompt = """You are a professional podcast script writer creating a general daily digest.

Create a compelling summary that:
1. Introduces the digest and today's date
2. Provides key insights from the episode transcripts provided
3. Groups related themes and topics naturally
4. Maintains a conversational, engaging tone
5. Concludes with a brief summary and sign-off
6. Keeps content under 1000 words

Focus on extracting the most interesting and valuable insights across all episodes."""

        user_prompt = f"""Create a general podcast digest for {digest_date.strftime('%B %d, %Y')} from these episodes:

IMPORTANT - TRANSCRIPT AVAILABILITY:
You have COMPLETE access to ALL {len(transcripts)} episode transcripts provided below. Each transcript contains the full content needed to discuss that episode in detail. DO NOT claim you don't have access to any transcript, as all transcripts are fully provided.

"""
        for i, transcript in enumerate(transcripts, 1):
            user_prompt += f"""
Episode {i}: {transcript['title']} (Published: {transcript['published_date']})
Transcript: {transcript['transcript'][:transcript_limit]}

"""

        user_prompt += "\nCreate an engaging general digest that highlights the most interesting insights from these episodes. You have full transcripts for all episodes above - discuss each episode's content directly."

        try:
            # For general summary, temporarily override max_output_tokens
            original_max = self.max_output_tokens
            self.max_output_tokens = min(int(self.max_output_tokens), 2000)
            script = self._call_llm(system_prompt, user_prompt)
            self.max_output_tokens = original_max
            word_count = len(script.split())
            
            if word_count > 1200:
                logger.warning(f"General summary script ({word_count} words) exceeds recommended 1000 words")
            
            logger.info(f"Generated general summary script: {word_count} words")
            return script, word_count
            
        except Exception as e:
            logger.error(f"{self.ai_model} error for general summary: {e}")
            # Fallback to basic summary
            basic_script = f"""# General Summary - {digest_date.strftime('%B %d, %Y')}

Hello and welcome to your general podcast digest for {digest_date.strftime('%B %d, %Y')}.

Today we have {len(episodes)} interesting episodes that contain valuable insights:

"""
            for episode in episodes:
                basic_script += f"- **{episode.title}** (Published: {episode.published_date.strftime('%B %d, %Y')})\n"
            
            basic_script += """
While we encountered some technical issues generating a detailed summary, these episodes are worth checking out directly.

Thank you for your understanding, and we'll see you tomorrow with fresh insights!

---
*This digest was automatically generated from episodes that didn't meet specific topic thresholds.*"""
            
            return basic_script, len(basic_script.split())
    
    def mark_episode_as_digested(self, episode: Episode) -> None:
        """Mark episode as digested and move transcript to digested folder"""
        logger.info(f"Marking episode {episode.id} as digested: {episode.title}")
        
        # Update episode status in database
        self.episode_repo.update_status_by_id(episode.id, 'digested')
        
        # Move transcript file to digested folder if it exists
        if episode.transcript_path and Path(episode.transcript_path).exists():
            transcript_path = Path(episode.transcript_path)
            # Avoid nesting digested/digested when already archived
            if transcript_path.parent.name == 'digested':
                logger.debug("Transcript already in digested folder; leaving in place")
                return
            digested_dir = transcript_path.parent / 'digested'
            digested_dir.mkdir(exist_ok=True)
            new_path = digested_dir / transcript_path.name
            try:
                if transcript_path != new_path:
                    transcript_path.replace(new_path)
                self.episode_repo.update_transcript_path(episode.id, str(new_path))
                logger.info(f"Moved transcript to: {new_path}")
            except Exception as e:
                logger.error(f"Failed to move transcript for episode {episode.id}: {e}")
    
    def mark_digest_episodes_as_digested(self, digest: Digest) -> None:
        """Mark all episodes in a digest as digested using join table.

        Issue #10: Uses digest_episode_links as single source of truth.
        """
        if not digest.id:
            return

        # Use join table as source of truth for episode IDs
        episode_ids = []
        if self.digest_episode_link_repo:
            episode_ids = self.digest_episode_link_repo.get_episode_ids_for_digest(digest.id)

        for episode_id in episode_ids:
            episode = self.episode_repo.get_by_id(episode_id)
            if episode:
                self.mark_episode_as_digested(episode)
