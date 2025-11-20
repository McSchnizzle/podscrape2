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
from ..config.config_manager import ConfigManager
from ..config.web_config import WebConfigManager

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

        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        # Per-digest episode cap (from web config if available)
        self.max_episodes_per_digest = 5
        if self.web_config:
            try:
                self.max_episodes_per_digest = int(self.web_config.get_setting('content_filtering', 'max_episodes_per_digest', 5))
            except Exception:
                pass
        
        # Minimum episodes required to generate digest (from web config if available)
        self.min_episodes_per_digest = 1
        if self.web_config:
            try:
                self.min_episodes_per_digest = int(self.web_config.get_setting('content_filtering', 'min_episodes_per_digest', 1))
            except Exception:
                pass
        
        # Load topic configuration
        self.topics = self.config.get_topics()
        self.score_threshold = self.config.get_score_threshold()
        self.max_words = self.config.get_max_words_per_script()

        # Load AI configuration for digest generation
        if self.web_config:
            self.ai_model = self.web_config.get_setting('ai_digest_generation', 'model', 'gpt-5')
            self.max_output_tokens = self.web_config.get_setting('ai_digest_generation', 'max_output_tokens', 25000)
            self.max_input_tokens = self.web_config.get_setting('ai_digest_generation', 'max_input_tokens', 150000)

            # Validate token limits against model capabilities
            self.max_output_tokens = self._validate_and_adjust_token_limit(self.ai_model, self.max_output_tokens, 'max_output')
            self.max_input_tokens = self._validate_and_adjust_token_limit(self.ai_model, self.max_input_tokens, 'max_input')
        else:
            self.ai_model = 'gpt-5'
            self.max_output_tokens = 25000
            self.max_input_tokens = 150000

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

    def _validate_and_adjust_token_limit(self, model: str, requested_tokens: int, limit_type: str) -> int:
        """Validate and adjust token limit based on model capabilities"""
        if not self.web_config:
            return requested_tokens

        max_limit = self.web_config.get_model_limit('openai', model, limit_type)
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

    def _calculate_transcript_limit(self, num_episodes: int) -> int:
        """Calculate transcript character limit based on configured input token cap"""
        if not getattr(self, 'max_input_tokens', None):
            return 8000

        available_input_tokens = int(self.max_input_tokens * 0.8)
        available_chars = available_input_tokens * 4
        chars_per_episode = available_chars // max(num_episodes, 1)
        return min(max(chars_per_episode, 2000), 20000)

    def _generate_dialogue_script(self, topic: str, episodes: List[Episode],
                                  digest_date: date, instruction: TopicInstruction) -> Tuple[str, int]:
        """
        Generate dialogue-style script for multi-voice delivery (v3 with audio tags).
        Target: 15,000-20,000 characters with SPEAKER_1/SPEAKER_2 labels.

        Args:
            topic: Topic name
            episodes: List of episodes to include
            digest_date: Date of digest
            instruction: Topic configuration with voice_config

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
        for episode in episodes:
            if not episode.transcript_content or not episode.transcript_content.strip():
                logger.error(f"No transcript content in database for episode: {episode.title}")
                raise ScriptGenerationError(f"Episode {episode.title} has no transcript content in database")

            transcripts.append({
                'title': episode.title,
                'published_date': episode.published_date.strftime('%Y-%m-%d'),
                'transcript': episode.transcript_content,
                'score': episode.scores.get(topic, 0.0) if episode.scores else 0.0
            })

        transcript_limit = self._calculate_transcript_limit(len(transcripts))

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

REQUIREMENTS:
- Target 15,000-20,000 characters (this is measured in characters, not words)
- Create engaging dialogue between {speaker_1_name} and {speaker_2_name}
- Use audio tags liberally to add emotional warmth and expression
- Follow the structure outlined in the topic instructions
- Include episode titles and dates when relevant
- Focus on the most important insights and developments
- Maintain natural conversational flow with appropriate turn-taking

Date: {digest_date.strftime('%B %d, %Y')}
Topic: {topic}
Episodes: {len(transcripts)}"""

        user_prompt = f"""Create a dialogue-style digest script from these {len(transcripts)} episode(s):

"""

        for i, transcript_data in enumerate(transcripts, 1):
            user_prompt += f"""Episode {i}: "{transcript_data['title']}" (Published: {transcript_data['published_date']}, Relevance Score: {transcript_data['score']:.2f})

Transcript:
{transcript_data['transcript'][:transcript_limit]}

---

"""

        user_prompt += f"""Generate a dialogue script between SPEAKER_1 ({speaker_1_name}) and SPEAKER_2 ({speaker_2_name}) that covers the key insights from these episodes.

CRITICAL: Use EXACT format for EVERY turn:
SPEAKER_1: [audio_tag] dialogue text...
SPEAKER_2: [audio_tag] dialogue text...

The colon MUST come immediately after the speaker number, BEFORE the audio tag.

Target 15,000-20,000 characters. Use audio tags like [excited], [thoughtful], [concerned], [hopeful], [curious] to add emotional expression."""

        try:
            response = self.client.responses.create(
                model=self.ai_model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                reasoning={"effort": "medium"},
                max_output_tokens=self.max_output_tokens
            )

            script_content = response.output_text
            char_count = len(script_content)

            # Validate and fix dialogue format (v1.96 - enforce SPEAKER_1: format)
            script_content, fixed = self._validate_and_fix_dialogue_format(script_content)
            if fixed:
                logger.warning(f"Auto-corrected dialogue format issues in generated script")
                char_count = len(script_content)  # Update char count after fixes

            # Validate character count
            if char_count < 15000:
                logger.warning(f"Dialogue script is shorter than target: {char_count} < 15,000 characters")
            elif char_count > 20000:
                logger.warning(f"Dialogue script exceeds target: {char_count} > 20,000 characters")

            logger.info(f"Generated dialogue script for {topic}: {char_count} characters from {len(episodes)} episodes")
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

    def _generate_narrative_script(self, topic: str, episodes: List[Episode],
                                   digest_date: date, instruction: TopicInstruction) -> Tuple[str, int]:
        """
        Generate narrative-style script for single-voice delivery (Turbo v2.5).
        Target: 10,000-15,000 characters with TTS optimization.

        Args:
            topic: Topic name
            episodes: List of episodes to include
            digest_date: Date of digest
            instruction: Topic configuration

        Returns:
            Tuple of (script_content, character_count)
        """
        # Prepare episode transcripts
        transcripts = []
        for episode in episodes:
            if not episode.transcript_content or not episode.transcript_content.strip():
                logger.error(f"No transcript content in database for episode: {episode.title}")
                raise ScriptGenerationError(f"Episode {episode.title} has no transcript content in database")

            transcripts.append({
                'title': episode.title,
                'published_date': episode.published_date.strftime('%Y-%m-%d'),
                'transcript': episode.transcript_content,
                'score': episode.scores.get(topic, 0.0) if episode.scores else 0.0
            })

        transcript_limit = self._calculate_transcript_limit(len(transcripts))

        # Generate narrative script with TTS optimization for ElevenLabs Turbo v2.5
        system_prompt = f"""You are a professional podcast script writer creating a narrative digest for the topic "{topic}".

TOPIC INSTRUCTIONS:
{instruction.content}

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

"""

        for i, transcript_data in enumerate(transcripts, 1):
            user_prompt += f"""Episode {i}: "{transcript_data['title']}" (Published: {transcript_data['published_date']}, Relevance Score: {transcript_data['score']:.2f})

Transcript:
{transcript_data['transcript'][:transcript_limit]}

---

"""

        user_prompt += f"""Generate a TTS-optimized narrative script following ALL the text normalization rules above. Target 10,000-15,000 characters. Remember: expand ALL numbers, dates, and abbreviations to their full spoken form."""

        try:
            response = self.client.responses.create(
                model=self.ai_model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                reasoning={"effort": "medium"},
                max_output_tokens=self.max_output_tokens
            )

            script_content = response.output_text
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
        
        # Determine cap
        cap = max_episodes if isinstance(max_episodes, int) and max_episodes > 0 else self.max_episodes_per_digest
        # If we have more than cap, take the highest scoring ones
        if cap and len(all_qualifying) > cap:
            # Sort by score (highest first) and take top max_episodes
            sorted_episodes = sorted(
                all_qualifying, 
                key=lambda ep: ep.scores.get(topic, 0.0), 
                reverse=True
            )
            logger.info(f"Limiting {topic} episodes from {len(all_qualifying)} to {cap} (saving {len(all_qualifying) - cap} for future digests)")
            return sorted_episodes[:cap]
        
        return all_qualifying
    
    def generate_script(self, topic: str, episodes: List[Episode],
                       digest_date: date) -> Tuple[str, int]:
        """
        Generate digest script for topic using GPT-5.
        Routes to dialogue or narrative mode based on topic configuration.

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
            return self._generate_dialogue_script(topic, episodes, digest_date, instruction)
        else:
            logger.info(f"Generating NARRATIVE script for {topic} (single-voice TTS-optimized)")
            return self._generate_narrative_script(topic, episodes, digest_date, instruction)
    
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

        # Generate script
        script_content, word_count = self.generate_script(topic, episodes, digest_date)

        # Save script to file with timestamp for uniqueness
        digest_timestamp = datetime.now(UTC)
        script_path = self.save_script(topic, digest_date, script_content, word_count, digest_timestamp)

        # Create new digest (each run creates a unique digest with timestamp)
        digest = Digest(
            topic=topic,
            digest_date=digest_date,
            digest_timestamp=digest_timestamp,
            episode_ids=[ep.id for ep in episodes],
            episode_count=len(episodes),
            script_path=script_path,
            script_content=script_content,
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
        """Get undigested episodes for fallback general summary"""
        return self.episode_repo.get_undigested_episodes(
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
    
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
            digest = Digest(
                topic="General Summary",
                digest_date=digest_date,
                episode_ids=[ep.id for ep in episodes],
                episode_count=len(episodes),
                script_path=script_path,
                script_word_count=word_count,
                average_score=0.0  # No topic-specific score for general summary
            )
            
            digest_id = self.digest_repo.create(digest)
            digest.id = digest_id
            
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

"""
        for i, transcript in enumerate(transcripts, 1):
            user_prompt += f"""
Episode {i}: {transcript['title']} (Published: {transcript['published_date']})
Transcript: {transcript['transcript'][:transcript_limit]}

"""

        user_prompt += "\nCreate an engaging general digest that highlights the most interesting insights from these episodes."

        try:
            response = self.client.responses.create(
                model=self.ai_model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_output_tokens=min(self.max_output_tokens, 2000)
            )
            
            script = response.output_text
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
        """Mark all episodes in a digest as digested"""
        if not digest.episode_ids:
            return
        
        for episode_id in digest.episode_ids:
            episode = self.episode_repo.get_by_id(episode_id)
            if episode:
                self.mark_episode_as_digested(episode)
