"""
Script Generator for RSS Podcast Transcript Digest System.
Generates topic-based digest scripts from scored episodes using GPT-5.
"""

import os
import json
import logging
from datetime import date, datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import openai
from dataclasses import dataclass

from ..database.models import Episode, Digest, get_episode_repo, get_digest_repo
from ..config.config_manager import ConfigManager

logger = logging.getLogger(__name__)

@dataclass
class TopicInstruction:
    """Topic instruction loaded from markdown file"""
    name: str
    filename: str
    content: str
    voice_id: str
    active: bool
    description: str

class ScriptGenerationError(Exception):
    """Raised when script generation fails"""
    pass

class ScriptGenerator:
    """
    Generates topic-based digest scripts from scored episodes using GPT-5.
    Loads instructions from digest_instructions/ directory and enforces word limits.
    """
    
    def __init__(self, config_manager: ConfigManager = None):
        self.config = config_manager or ConfigManager()
        self.episode_repo = get_episode_repo()
        self.digest_repo = get_digest_repo()
        self.client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Load topic configuration
        self.topics = self.config.get_topics()
        self.score_threshold = self.config.get_score_threshold()
        self.max_words = self.config.get_max_words_per_script()
        
        # Load topic instructions
        self.topic_instructions = self._load_topic_instructions()
        
        # Create scripts directory
        self.scripts_dir = Path('data/scripts')
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_topic_instructions(self) -> Dict[str, TopicInstruction]:
        """Load topic instructions from digest_instructions/ directory"""
        instructions = {}
        instructions_dir = Path('digest_instructions')
        
        if not instructions_dir.exists():
            raise ScriptGenerationError(f"Instructions directory not found: {instructions_dir}")
        
        for topic in self.topics:
            if not topic.get('active', True):
                continue
            
            instruction_file = topic.get('instruction_file')
            if not instruction_file:
                logger.warning(f"No instruction file specified for topic: {topic['name']}")
                continue
            
            instruction_path = instructions_dir / instruction_file
            if not instruction_path.exists():
                logger.warning(f"Instruction file not found: {instruction_path}")
                continue
            
            try:
                with open(instruction_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                instructions[topic['name']] = TopicInstruction(
                    name=topic['name'],
                    filename=instruction_file,
                    content=content,
                    voice_id=topic.get('voice_id', ''),
                    active=topic.get('active', True),
                    description=topic.get('description', '')
                )
                
                logger.info(f"Loaded instructions for topic: {topic['name']}")
                
            except Exception as e:
                logger.error(f"Failed to load instructions for {topic['name']}: {e}")
                continue
        
        logger.info(f"Loaded instructions for {len(instructions)} topics")
        return instructions
    
    def get_qualifying_episodes(self, topic: str, start_date: date = None, 
                              end_date: date = None) -> List[Episode]:
        """Get episodes that qualify for digest generation (score >= threshold)"""
        return self.episode_repo.get_scored_episodes_for_topic(
            topic=topic,
            min_score=self.score_threshold,
            start_date=start_date,
            end_date=end_date
        )
    
    def generate_script(self, topic: str, episodes: List[Episode], 
                       digest_date: date) -> Tuple[str, int]:
        """
        Generate digest script for topic using GPT-5.
        Returns (script_content, word_count)
        """
        if topic not in self.topic_instructions:
            raise ScriptGenerationError(f"No instructions found for topic: {topic}")
        
        instruction = self.topic_instructions[topic]
        
        # Handle no content case
        if not episodes:
            return self._generate_no_content_script(topic, digest_date)
        
        # Prepare episode transcripts
        transcripts = []
        for episode in episodes:
            if episode.transcript_path and Path(episode.transcript_path).exists():
                with open(episode.transcript_path, 'r', encoding='utf-8') as f:
                    transcript = f.read()
                transcripts.append({
                    'title': episode.title,
                    'published_date': episode.published_date.strftime('%Y-%m-%d'),
                    'transcript': transcript,
                    'score': episode.scores.get(topic, 0.0) if episode.scores else 0.0
                })
        
        if not transcripts:
            logger.warning(f"No transcripts available for {len(episodes)} episodes")
            return self._generate_no_content_script(topic, digest_date)
        
        # Generate script using GPT-5
        system_prompt = f"""You are a professional podcast script writer creating a daily digest for the topic "{topic}".

INSTRUCTIONS:
{instruction.content}

REQUIREMENTS:
- Maximum {self.max_words:,} words
- Create a coherent narrative from the provided episode transcripts
- Follow the structure outlined in the topic instructions
- Maintain engaging, conversational tone suitable for audio
- Include episode titles and dates when relevant
- Focus on the most important insights and developments

Date: {digest_date.strftime('%B %d, %Y')}
Topic: {topic}
Episodes: {len(transcripts)}"""

        user_prompt = f"""Create a digest script from these {len(transcripts)} episode(s):

"""
        
        for i, transcript_data in enumerate(transcripts, 1):
            user_prompt += f"""Episode {i}: "{transcript_data['title']}" (Published: {transcript_data['published_date']}, Relevance Score: {transcript_data['score']:.2f})

Transcript:
{transcript_data['transcript'][:8000]}  # Limit transcript length for token management

---

"""
        
        user_prompt += f"""Generate a comprehensive digest script following the topic instructions. Maximum {self.max_words:,} words."""
        
        try:
            response = self.client.responses.create(
                model="gpt-5",  # Using GPT-5 with Responses API as specified
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                reasoning={"effort": "medium"},  # Medium effort for quality script generation
                max_output_tokens=8000  # GPT-5 supports much larger output tokens
            )
            
            script_content = response.output_text  # GPT-5 Responses API format
            word_count = len(script_content.split())
            
            # Validate word count
            if word_count > self.max_words:
                logger.warning(f"Generated script exceeds word limit: {word_count} > {self.max_words}")
                # Could implement truncation logic here if needed
            
            logger.info(f"Generated script for {topic}: {word_count} words from {len(episodes)} episodes")
            return script_content, word_count
            
        except Exception as e:
            logger.error(f"GPT-5 Responses API error for topic {topic}: {e}")
            raise ScriptGenerationError(f"Failed to generate script with GPT-5: {e}")
    
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
    
    def save_script(self, topic: str, digest_date: date, content: str, word_count: int) -> str:
        """Save script to file and return file path"""
        filename = f"{topic.replace(' ', '_')}_{digest_date.strftime('%Y%m%d')}.md"
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
                     start_date: date = None, end_date: date = None) -> Digest:
        """
        Create complete digest: find episodes, generate script, save to database.
        Returns created Digest object.
        """
        logger.info(f"Creating digest for {topic} on {digest_date}")
        
        # Check if digest already exists
        existing_digest = self.digest_repo.get_by_topic_date(topic, digest_date)
        if existing_digest and existing_digest.script_path:
            logger.info(f"Digest already exists for {topic} on {digest_date}")
            return existing_digest
        
        # Find qualifying episodes
        episodes = self.get_qualifying_episodes(topic, start_date, end_date)
        logger.info(f"Found {len(episodes)} qualifying episodes for {topic}")
        
        # Generate script
        script_content, word_count = self.generate_script(topic, episodes, digest_date)
        
        # Save script to file
        script_path = self.save_script(topic, digest_date, script_content, word_count)
        
        # Create or update digest in database
        if existing_digest:
            # Update existing
            self.digest_repo.update_script(existing_digest.id, script_path, word_count)
            existing_digest.script_path = script_path
            existing_digest.script_word_count = word_count
            return existing_digest
        else:
            # Create new digest
            digest = Digest(
                topic=topic,
                digest_date=digest_date,
                episode_ids=[ep.id for ep in episodes],
                episode_count=len(episodes),
                script_path=script_path,
                script_word_count=word_count,
                average_score=sum(ep.scores.get(topic, 0.0) for ep in episodes) / len(episodes) if episodes else 0.0
            )
            
            digest_id = self.digest_repo.create(digest)
            digest.id = digest_id
            
            logger.info(f"Created digest {digest_id} for {topic}: {word_count} words, {len(episodes)} episodes")
            return digest
    
    def create_daily_digests(self, digest_date: date, 
                            start_date: date = None, end_date: date = None) -> List[Digest]:
        """Create digests for all active topics for given date"""
        digests = []
        
        for topic_name in self.topic_instructions:
            try:
                digest = self.create_digest(topic_name, digest_date, start_date, end_date)
                digests.append(digest)
            except Exception as e:
                logger.error(f"Failed to create digest for {topic_name}: {e}")
                continue
        
        logger.info(f"Created {len(digests)} digests for {digest_date}")
        return digests