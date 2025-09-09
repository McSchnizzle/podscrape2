"""
Content Scoring System using GPT-5-mini for podcast transcript relevancy analysis.

This module provides GPT-5-mini powered content scoring that evaluates podcast transcripts 
against topic relevancy using structured JSON output with 0.0-1.0 scoring scale.

Key Features:
- GPT-5-mini Responses API integration with structured JSON output
- Batch processing for efficiency
- Topic-based scoring against config/topics.json
- Database storage with automatic status tracking
- Threshold-based filtering (≥0.65 for digest inclusion)
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
    
    def __init__(self, config_path: str = None):
        """
        Initialize content scorer with OpenAI API and topic configuration.
        
        Args:
            config_path: Path to topics.json config file
        """
        # Load OpenAI API key
        self.client = OpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),
            timeout=30.0  # 30 second timeout for testing
        )
        
        # Load topic configuration
        if config_path is None:
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / 'config' / 'topics.json'
        
        self.config = self._load_config(config_path)
        self.topics = [topic for topic in self.config['topics'] if topic.get('active', True)]
        self.score_threshold = self.config['settings']['score_threshold']
        
        logger.info(f"ContentScorer initialized with {len(self.topics)} active topics")
    
    def _load_config(self, config_path: Path) -> dict:
        """Load topics configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            raise
    
    def _create_scoring_prompt(self, transcript: str, topics: List[dict]) -> str:
        """
        Create GPT-5-mini prompt for transcript scoring.
        
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
            # Create prompt and schema
            prompt = self._create_scoring_prompt(cleaned_transcript, self.topics)
            schema = self._create_json_schema(self.topics)
            
            # Call GPT-5-mini using Responses API (correct format from gpt5-implementation-learnings.md)
            response = self.client.responses.create(
                model="gpt-5-mini",
                input=[
                    {"role": "user", "content": prompt}
                ],
                reasoning={"effort": "minimal"},  # Minimal effort for scoring tasks
                max_output_tokens=1000,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "content_scores",
                        "schema": schema,
                        "strict": True
                    }
                }
            )
            
            # Parse response using Responses API format
            scores_json = response.output_text
            scores = json.loads(scores_json)
            
            # Validate scores are within expected range
            for topic_name, score in scores.items():
                if not (0.0 <= score <= 1.0):
                    logger.warning(f"Score {score} for topic {topic_name} outside valid range [0.0, 1.0]")
                    scores[topic_name] = max(0.0, min(1.0, score))  # Clamp to valid range
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"Successfully scored {'episode ' + episode_id if episode_id else 'transcript'} with GPT-5-mini "
                       f"in {processing_time:.2f}s")
            
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