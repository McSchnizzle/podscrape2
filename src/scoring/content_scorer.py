"""
Content Scoring System using claude -p for podcast transcript relevancy analysis.

This module provides claude -p powered content scoring that evaluates podcast transcripts
against topic relevancy using JSON output with 0.0-1.0 scoring scale.

Key Features:
- claude -p integration via subprocess stdin
- Batch processing for efficiency
- Topic-based scoring against database topics
- Database storage with automatic status tracking
- Threshold-based filtering (≥0.65 for digest inclusion)
"""

import json
import logging
import os
import subprocess
# ┌─────────────────────────────────────────────────────────────────────┐
# │ PREVIOUS IMPLEMENTATION: OpenAI API (gpt-5-mini Responses API)      │
# │ To revert: uncomment 'from openai import OpenAI' below, restore     │
# │ self.client = OpenAI(...) in __init__, and restore the              │
# │ client.responses.create() block in score_transcript().             │
# │                                                                     │
# │ from openai import OpenAI                                           │
# └─────────────────────────────────────────────────────────────────────┘
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from src.config.config_manager import ConfigManager
from src.config.web_config import WebConfigManager, SettingsKeys

# Environment variables expected to be loaded by calling script via src.config.env

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class ScoringResult:
    """Result container for content scoring operation"""
    episode_id: str
    scores: Dict[str, float]
    processing_time: float
    success: bool
    error_message: Optional[str] = None

class ContentScorer:
    """
    GPT-5-mini powered content scorer for podcast transcripts.
    
    Evaluates transcripts against topic relevancy using structured JSON output
    with 0.0-1.0 scoring scale for each configured topic.
    """
    
    def __init__(self, config_path: str = None, config_manager: ConfigManager = None, web_config: Any = None):
        """
        Initialize content scorer with topic configuration.

        Args:
            config_path: Path to topics.json config file (legacy; topics now loaded from DB)
        """
        self.web_config = web_config or self._safe_create_web_config()

        # ┌─────────────────────────────────────────────────────────────────────┐
        # │ PREVIOUS IMPLEMENTATION: OpenAI client initialization               │
        # │ To revert: uncomment below                                          │
        # │                                                                     │
        # │ openai_timeout = self.web_config.get_setting(                       │
        # │     SettingsKeys.ApiTimeouts.CATEGORY,                              │
        # │     SettingsKeys.ApiTimeouts.OPENAI_TIMEOUT, 120) if ...           │
        # │ self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'),           │
        # │                      timeout=float(openai_timeout))                 │
        # └─────────────────────────────────────────────────────────────────────┘

        # Determine config directory
        config_dir = None
        if config_path is not None:
            config_dir = str(Path(config_path).parent)

        self.config_manager = config_manager or ConfigManager(config_dir=config_dir or 'config', web_config=self.web_config)

        # Load topics and score threshold via ConfigManager
        self.topics = self.config_manager.get_topics()
        self.score_threshold = self.config_manager.get_score_threshold()

        # Kept for legacy reference (not used by claude -p path)
        if self.web_config:
            self.ai_model = self.web_config.get_setting(SettingsKeys.AIContentScoring.CATEGORY, SettingsKeys.AIContentScoring.MODEL, "gpt-5-mini")
            self.max_tokens = self.web_config.get_setting(SettingsKeys.AIContentScoring.CATEGORY, SettingsKeys.AIContentScoring.MAX_TOKENS, 1000)
            self.max_episodes_per_batch = self.web_config.get_setting(SettingsKeys.AIContentScoring.CATEGORY, SettingsKeys.AIContentScoring.MAX_EPISODES_PER_BATCH, 10)
        else:
            self.ai_model = "gpt-5-mini"
            self.max_tokens = 1000
            self.max_episodes_per_batch = 10

        logger.info(f"ContentScorer initialized (claude -p mode) with {len(self.topics)} active topics")
    
    def _safe_create_web_config(self) -> Optional[WebConfigManager]:
        try:
            return WebConfigManager()
        except Exception:
            return None

    def _validate_and_adjust_token_limit(self, model: str, requested_tokens: int) -> int:
        """Validate and adjust token limit based on model capabilities"""
        if not self.web_config:
            return requested_tokens

        # Get model's maximum output token limit
        max_limit = self.web_config.get_model_limit('openai', model, 'max_output')
        if max_limit > 0 and requested_tokens > max_limit:
            logger.warning(f"Requested {requested_tokens} tokens exceeds {model} limit of {max_limit}, adjusting to {max_limit}")
            return max_limit

        return requested_tokens

    def _get_reasoning_effort(self, model: str) -> str:
        """
        Determine appropriate reasoning effort based on model capabilities.

        GPT-5.2* models only support 'medium' reasoning effort.
        Other models (like gpt-5-mini) support 'minimal' for faster/cheaper scoring.
        """
        if model.startswith("gpt-5.2"):
            return "medium"
        return "minimal"

    @staticmethod
    def _call_claude_p(prompt: str, timeout: int = 300) -> str:
        """Call claude -p with prompt via stdin."""
        claude_path = os.path.expanduser("~/.local/bin/claude")
        if not os.path.exists(claude_path):
            claude_path = "claude"
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        env.pop("ANTHROPIC_API_KEY", None)  # Force Max subscription, not API billing
        result = subprocess.run(
            [claude_path, "-p", "--model", "sonnet", "--effort", "medium",
             "--tools", "", "--no-session-persistence", "-"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(f"claude -p failed (exit {result.returncode}): {result.stderr[:500]}")
        return result.stdout.strip()

    def _load_scoring_skill(self) -> str:
        """Load the topic scoring skill from .claude/commands/."""
        skill_path = Path(__file__).parent.parent.parent / '.claude' / 'commands' / 'score-topic.md'
        if skill_path.exists():
            return skill_path.read_text()
        # Embedded fallback so et01 works even if skill file isn't present
        return """You are an expert content analyst. Score the podcast transcript's relevance to each topic on a 0.0-1.0 scale.
Return ONLY a valid JSON object with one key per topic and a float score. No markdown, no explanation.
Rubric: 0.0-0.3 not relevant, 0.4-0.6 somewhat relevant, 0.7-0.8 highly relevant, 0.9-1.0 central topic."""

    def _build_claude_p_scoring_prompt(self, transcript: str, topics: List[dict]) -> str:
        """Build prompt for claude -p scoring."""
        skill_content = self._load_scoring_skill()

        topic_lines = "\n".join(
            f"- {t['name']}: {t['description']}" for t in topics
        )

        # Use more transcript than the old OpenAI path (was 4000, now 6000)
        excerpt = transcript[:6000]
        if len(transcript) > 6000:
            excerpt += "..."

        return (
            f"{skill_content}\n\n"
            f"## Topics to Score\n\n"
            f"{topic_lines}\n\n"
            f"## Transcript\n\n"
            f"{excerpt}"
        )

    def _score_with_claude_p(self, transcript: str, topics: List[dict]) -> Dict[str, float]:
        """Score transcript via claude -p, returns {topic_name: score} dict."""
        prompt = self._build_claude_p_scoring_prompt(transcript, topics)
        raw = self._call_claude_p(prompt)

        # Strip markdown code fences if present
        if raw.startswith('```json'):
            raw = raw.replace('```json', '').replace('```', '').strip()
        elif raw.startswith('```'):
            raw = raw.replace('```', '').strip()

        scores = json.loads(raw)

        # Validate and clamp all scores; fill missing topics with 0.0
        result = {}
        for t in topics:
            name = t['name']
            score = float(scores.get(name, 0.0))
            if not (0.0 <= score <= 1.0):
                logger.warning(f"Score {score} for '{name}' outside [0,1], clamping")
                score = max(0.0, min(1.0, score))
            result[name] = score

        return result

    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ LEGACY: _create_scoring_prompt and _create_json_schema (OpenAI)    │
    # │ Kept for reference. Not called by the claude -p path.               │
    # └─────────────────────────────────────────────────────────────────────┘
    def _create_scoring_prompt(self, transcript: str, topics: List[dict]) -> str:
        """
        Create AI model prompt for transcript scoring.
        
        Args:
            transcript: The podcast transcript text
            topics: List of topic configurations
            
        Returns:
            Formatted prompt string
        """
        topic_descriptions = []
        for topic in topics:
            topic_descriptions.append(f"- {topic['name']}: {topic['description']}")
        
        prompt = f"""You are an expert content analyst evaluating podcast transcript relevancy.

Analyze this podcast transcript and score its relevance to each topic on a scale of 0.0 to 1.0:

Topics to evaluate:
{chr(10).join(topic_descriptions)}

Scoring Guidelines:
- 0.0-0.3: Not relevant or only tangentially mentioned
- 0.4-0.6: Somewhat relevant, touches on topic but not central
- 0.7-0.8: Highly relevant, significant discussion of topic
- 0.9-1.0: Extremely relevant, topic is central to the content

Transcript to analyze:
{transcript[:4000]}{"..." if len(transcript) > 4000 else ""}

Provide scores for each topic as a JSON object with topic names as keys and scores as values."""
        
        return prompt
    
    def _create_json_schema(self, topics: List[dict]) -> dict:
        """
        Create JSON schema for structured GPT-5-mini output.
        
        Args:
            topics: List of topic configurations
            
        Returns:
            JSON schema dictionary
        """
        properties = {}
        for topic in topics:
            properties[topic['name']] = {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": f"Relevance score for {topic['name']} (0.0-1.0)"
            }
        
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties.keys()),
            "additionalProperties": False
        }
    
    def _clean_transcript(self, transcript: str) -> str:
        """
        Clean transcript by removing advertisement portions.
        Removes first 5% and last 5% where ads typically appear.
        """
        if not transcript or len(transcript) < 500:
            return transcript
            
        # Calculate trim points (5% from each end)
        total_length = len(transcript)
        trim_amount = int(total_length * 0.05)
        
        # Trim from both ends
        start_pos = trim_amount
        end_pos = total_length - trim_amount
        
        cleaned = transcript[start_pos:end_pos]
        
        # Log the cleaning results
        reduction_pct = (trim_amount * 2 / total_length * 100) if total_length > 0 else 0
        
        logger.info(f"Transcript cleaning: {total_length} → {len(cleaned)} chars ({reduction_pct:.1f}% reduction)")
        
        return cleaned

    def score_transcript(self, transcript: str, episode_id: str = None) -> ScoringResult:
        """
        Score a single transcript against all active topics.
        
        Args:
            transcript: The podcast transcript text
            episode_id: Optional episode identifier for logging
            
        Returns:
            ScoringResult with scores and metadata
        """
        start_time = datetime.now()

        # Clean transcript to remove advertisements and sponsor content
        cleaned_transcript = self._clean_transcript(transcript)

        try:
            scores = self._score_with_claude_p(cleaned_transcript, self.topics)

            processing_time = (datetime.now() - start_time).total_seconds()
            label = f"episode {episode_id}" if episode_id else "transcript"
            logger.info(f"Scored {label} via claude -p in {processing_time:.2f}s: "
                        f"{', '.join(f'{k}={v:.2f}' for k, v in scores.items())}")

            return ScoringResult(
                episode_id=episode_id or "unknown",
                scores=scores,
                processing_time=processing_time,
                success=True
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"Failed to score transcript: {e}"
            logger.error(error_msg)

            return ScoringResult(
                episode_id=episode_id or "unknown",
                scores={},
                processing_time=processing_time,
                success=False,
                error_message=error_msg
            )

        # ┌─────────────────────────────────────────────────────────────────────┐
        # │ PREVIOUS IMPLEMENTATION: OpenAI Responses API scoring               │
        # │ To revert: replace the try block above with:                        │
        # │                                                                     │
        # │     prompt = self._create_scoring_prompt(cleaned_transcript, ...)   │
        # │     schema = self._create_json_schema(self.topics)                  │
        # │     reasoning_effort = self._get_reasoning_effort(self.ai_model)    │
        # │     response = self.client.responses.create(                        │
        # │         model=self.ai_model,                                        │
        # │         input=[{"role": "user", "content": prompt}],               │
        # │         reasoning={"effort": reasoning_effort},                     │
        # │         max_output_tokens=self.max_tokens,                          │
        # │         text={"format": {"type": "json_schema", ...}}               │
        # │     )                                                               │
        # │     scores = json.loads(response.output_text)                       │
        # └─────────────────────────────────────────────────────────────────────┘
    
    def score_transcript_file(self, transcript_path: Path, episode_id: str = None) -> ScoringResult:
        """
        Score a transcript from file.
        
        Args:
            transcript_path: Path to transcript file
            episode_id: Optional episode identifier for logging
            
        Returns:
            ScoringResult with scores and metadata
        """
        try:
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript = f.read()
            
            return self.score_transcript(transcript, episode_id)
            
        except Exception as e:
            error_msg = f"Failed to read transcript file {transcript_path}: {e}"
            logger.error(error_msg)
            
            return ScoringResult(
                episode_id=episode_id or "unknown",
                scores={},
                processing_time=0.0,
                success=False,
                error_message=error_msg
            )
    
    def batch_score_episodes(self, episodes: List[tuple], max_batch_size: int = 10) -> List[ScoringResult]:
        """
        Score multiple episodes in batches for efficiency.
        
        Args:
            episodes: List of (episode_id, transcript_path) tuples
            max_batch_size: Maximum episodes to process in one batch
            
        Returns:
            List of ScoringResult objects
        """
        results = []
        total_episodes = len(episodes)
        
        logger.info(f"Starting batch scoring of {total_episodes} episodes")
        
        for i in range(0, total_episodes, max_batch_size):
            batch = episodes[i:i + max_batch_size]
            batch_num = (i // max_batch_size) + 1
            total_batches = (total_episodes + max_batch_size - 1) // max_batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} episodes)")
            
            for episode_id, transcript_path in batch:
                result = self.score_transcript_file(Path(transcript_path), episode_id)
                results.append(result)
                
                if result.success:
                    logger.info(f"Episode {episode_id}: {result.scores}")
                else:
                    logger.error(f"Episode {episode_id}: {result.error_message}")
        
        successful = sum(1 for r in results if r.success)
        logger.info(f"Batch scoring complete: {successful}/{total_episodes} episodes scored successfully")
        
        return results
    
    def get_qualifying_episodes(self, scored_episodes: List[tuple], topic: str) -> List[tuple]:
        """
        Filter episodes that meet the score threshold for a specific topic.
        
        Args:
            scored_episodes: List of (episode_id, scores_dict) tuples
            topic: Topic name to filter by
            
        Returns:
            List of (episode_id, score) tuples that meet threshold
        """
        qualifying = []
        
        for episode_id, scores in scored_episodes:
            if topic in scores and scores[topic] >= self.score_threshold:
                qualifying.append((episode_id, scores[topic]))
        
        # Sort by score descending
        qualifying.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(f"Found {len(qualifying)} episodes qualifying for topic '{topic}' "
                   f"(threshold: {self.score_threshold})")
        
        return qualifying
    
    def get_statistics(self, results: List[ScoringResult]) -> dict:
        """
        Calculate scoring statistics from batch results.
        
        Args:
            results: List of ScoringResult objects
            
        Returns:
            Dictionary with statistics
        """
        successful_results = [r for r in results if r.success]
        
        if not successful_results:
            return {
                "total_episodes": len(results),
                "successful_scores": 0,
                "failed_scores": len(results),
                "average_processing_time": 0.0,
                "topic_statistics": {}
            }
        
        # Calculate overall statistics
        total_time = sum(r.processing_time for r in successful_results)
        avg_time = total_time / len(successful_results)
        
        # Calculate topic-specific statistics
        topic_stats = {}
        for topic in self.topics:
            topic_name = topic['name']
            scores = [r.scores.get(topic_name, 0.0) for r in successful_results]
            
            topic_stats[topic_name] = {
                "average_score": sum(scores) / len(scores) if scores else 0.0,
                "max_score": max(scores) if scores else 0.0,
                "min_score": min(scores) if scores else 0.0,
                "qualifying_episodes": sum(1 for s in scores if s >= self.score_threshold)
            }
        
        return {
            "total_episodes": len(results),
            "successful_scores": len(successful_results),
            "failed_scores": len(results) - len(successful_results),
            "average_processing_time": avg_time,
            "topic_statistics": topic_stats
        }

def create_content_scorer(config_path: str = None) -> ContentScorer:
    """
    Factory function to create ContentScorer instance.
    
    Args:
        config_path: Optional path to topics configuration file
        
    Returns:
        ContentScorer instance
    """
    return ContentScorer(config_path)
