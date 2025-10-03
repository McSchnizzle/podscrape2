"""
Metadata Generator for RSS Podcast Transcript Digest System.
Generates episode titles and summaries from digest scripts using GPT-5.
"""

import os
import json
import logging
import openai
from datetime import datetime, date
from typing import Dict, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass

from ..config.web_config import WebConfigManager

logger = logging.getLogger(__name__)

@dataclass
class EpisodeMetadata:
    """Generated episode metadata"""
    title: str
    summary: str
    duration_estimate: Optional[str] = None
    keywords: Optional[str] = None
    category: Optional[str] = None

class MetadataGenerationError(Exception):
    """Raised when metadata generation fails"""
    pass

class MetadataGenerator:
    """
    Generates podcast episode metadata from digest scripts using configurable AI models.
    Creates compelling titles, summaries, and other metadata for RSS feed.
    """
    
    def __init__(self, web_config: WebConfigManager = None):
        self.web_config = web_config or self._safe_create_web_config()
        self.client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError("OPENAI_API_KEY environment variable is required")

        # Load AI configuration for metadata generation
        if self.web_config:
            self.ai_model = self.web_config.get_setting("ai_metadata_generation", "model", "gpt-5-mini")
            self.max_title_tokens = self.web_config.get_setting("ai_metadata_generation", "max_title_tokens", 50)
            self.max_summary_tokens = self.web_config.get_setting("ai_metadata_generation", "max_summary_tokens", 200)
            self.max_description_tokens = self.web_config.get_setting("ai_metadata_generation", "max_description_tokens", 500)

            # Validate token limits against model capabilities
            self.max_title_tokens = self._validate_and_adjust_token_limit(self.ai_model, self.max_title_tokens)
            self.max_summary_tokens = self._validate_and_adjust_token_limit(self.ai_model, self.max_summary_tokens)
            self.max_description_tokens = self._validate_and_adjust_token_limit(self.ai_model, self.max_description_tokens)
        else:
            self.ai_model = "gpt-5-mini"
            self.max_title_tokens = 50
            self.max_summary_tokens = 200
            self.max_description_tokens = 500

        logger.info(f"MetadataGenerator initialized with model: {self.ai_model}, title: {self.max_title_tokens}, summary: {self.max_summary_tokens}, description: {self.max_description_tokens} tokens")

    def _safe_create_web_config(self) -> Optional[WebConfigManager]:
        """Safely create web config, return None if not available"""
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

    def _extract_script_content(self, script_path: str) -> str:
        """Extract clean content from script file for analysis"""
        script_file = Path(script_path)
        if not script_file.exists():
            raise MetadataGenerationError(f"Script file not found: {script_path}")
        
        with open(script_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract main content, skip headers and metadata
        lines = content.split('\n')
        content_lines = []
        skip_metadata = False
        
        for line in lines:
            stripped = line.strip()
            
            # Skip markdown headers at the start
            if stripped.startswith('#'):
                continue
            
            # Skip metadata blocks
            if stripped.startswith('---') and stripped.endswith('---'):
                skip_metadata = not skip_metadata
                continue
            if skip_metadata:
                continue
            
            # Skip empty lines at start
            if not content_lines and not stripped:
                continue
            
            # Add content line
            if stripped:
                content_lines.append(stripped)
        
        return ' '.join(content_lines)
    
    def _clean_script_content(self, content: str) -> str:
        """Clean script content (remove markdown headers, metadata blocks)"""
        lines = content.split('\n')
        content_lines = []
        skip_metadata = False

        for line in lines:
            stripped = line.strip()

            # Skip markdown headers at the start
            if stripped.startswith('#'):
                continue

            # Skip metadata blocks
            if stripped.startswith('---') and stripped.endswith('---'):
                skip_metadata = not skip_metadata
                continue
            if skip_metadata:
                continue

            # Skip empty lines at start
            if not content_lines and not stripped:
                continue

            # Add content line
            if stripped:
                content_lines.append(stripped)

        return ' '.join(content_lines)

    def generate_metadata_from_content(self, script_content: str, topic: str,
                                      digest_date: date) -> EpisodeMetadata:
        """Generate episode metadata from script content (database-first)"""
        logger.info(f"Generating metadata for {topic} digest")

        # Clean script content (remove markdown headers, metadata blocks)
        cleaned_content = self._clean_script_content(script_content)
        content_length = len(cleaned_content)

        # Truncate if too long for API (generous limit for GPT-5-mini context)
        if content_length > 15000:
            cleaned_content = cleaned_content[:15000] + "..."
            logger.info(f"Truncated script content from {content_length} to {len(cleaned_content)} characters")
        
        # Generate metadata using configured AI model
        system_prompt = f"""You are a professional podcast producer creating metadata for a daily digest podcast.

Topic: {topic}
Date: {digest_date.strftime('%B %d, %Y')}

Generate compelling podcast episode metadata that will attract listeners and work well in podcast apps and RSS feeds.

Return ONLY a valid JSON object with these fields:
- title: Compelling episode title (max 60 characters, include date)
- summary: Engaging 2-3 sentence summary for podcast apps (max 200 characters) 
- keywords: Comma-separated relevant keywords for discovery
- category: Primary category (Technology, Society, News, etc.)

Make the title and summary appealing to busy professionals who want quick, valuable insights."""

        user_prompt = f"""Create podcast metadata for this {topic} daily digest:

CONTENT: {cleaned_content}

Generate metadata that accurately reflects the content and would attract the target audience."""

        try:
            logger.info(f"Calling {self.ai_model} for metadata generation...")
            
            response = self.client.responses.create(
                model=self.ai_model,  # Use configured model
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                reasoning={"effort": "minimal"},
                max_output_tokens=self.max_description_tokens,  # Use configured token limit
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "EpisodeMetadata",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string", "maxLength": 80},
                                "summary": {"type": "string", "maxLength": 250},
                                "keywords": {"type": "string", "maxLength": 100},
                                "category": {"type": "string", "maxLength": 50}
                            },
                            "required": ["title", "summary", "keywords", "category"],
                            "additionalProperties": False
                        },
                        "strict": True
                    }
                }
            )
            
            metadata_json = response.output_text.strip()

            # Log token usage information
            if hasattr(response, 'usage'):
                usage = response.usage
                logger.info(f"OpenAI API usage - Model: {self.ai_model}, "
                           f"Input tokens: {getattr(usage, 'input_tokens', 'unknown')}, "
                           f"Output tokens: {getattr(usage, 'output_tokens', 'unknown')}, "
                           f"Total tokens: {getattr(usage, 'total_tokens', 'unknown')}")
            else:
                logger.info(f"OpenAI API call completed - Model: {self.ai_model}, "
                           f"Max description tokens: {self.max_description_tokens}")

            # Clean up JSON if it has markdown formatting
            if metadata_json.startswith('```json'):
                metadata_json = metadata_json.replace('```json', '').replace('```', '').strip()
            elif metadata_json.startswith('```'):
                metadata_json = metadata_json.replace('```', '').strip()

            # Parse JSON response
            try:
                metadata_dict = json.loads(metadata_json)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {metadata_json}")
                raise MetadataGenerationError(f"Invalid JSON response from {self.ai_model}: {e}")
            
            # Validate required fields
            required_fields = ['title', 'summary', 'keywords', 'category']
            for field in required_fields:
                if field not in metadata_dict:
                    logger.warning(f"Missing field '{field}' in response, using default")
                    metadata_dict[field] = self._get_default_value(field, topic, digest_date)
            
            # Create metadata object
            metadata = EpisodeMetadata(
                title=metadata_dict['title'][:80],  # Ensure max length
                summary=metadata_dict['summary'][:250],  # Ensure max length
                keywords=metadata_dict['keywords'][:100],  # Reasonable limit
                category=metadata_dict['category'][:50]  # Reasonable limit
            )
            
            logger.info(f"Generated metadata - Title: '{metadata.title}', Category: {metadata.category}")
            return metadata
            
        except Exception as e:
            logger.error(f"{self.ai_model} metadata generation failed: {e}")

            # Fallback to generated metadata (using content-based fallback)
            return self._generate_fallback_metadata_from_content(cleaned_content, topic, digest_date)

    def generate_metadata_for_script(self, script_path: str, topic: str,
                                   digest_date: date) -> EpisodeMetadata:
        """Generate episode metadata from script file (legacy - prefer generate_metadata_from_content)"""
        logger.info(f"Generating metadata for script: {Path(script_path).name}")

        # Extract script content from file
        script_content = self._extract_script_content(script_path)

        # Use the content-based method
        return self.generate_metadata_from_content(script_content, topic, digest_date)
    
    def _get_default_value(self, field: str, topic: str, digest_date: date) -> str:
        """Get default value for missing metadata fields"""
        defaults = {
            'title': f"{topic} Daily Digest - {digest_date.strftime('%B %d, %Y')}",
            'summary': f"Your daily digest of the most important {topic.lower()} insights and developments.",
            'keywords': f"{topic.lower()}, daily digest, news, insights",
            'category': "Technology" if "tech" in topic.lower() or "ai" in topic.lower() else "Society"
        }
        return defaults.get(field, "Unknown")
    
    def _generate_fallback_metadata_from_content(self, content: str, topic: str,
                                                 digest_date: date) -> EpisodeMetadata:
        """Generate basic metadata from content when AI model fails (database-first)"""
        logger.info("Using fallback metadata generation")

        # Simple keyword extraction from content
        try:
            words = content.lower().split()
            common_words = set(['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'this', 'that', 'is', 'are', 'was', 'were', 'been', 'have', 'has', 'had', 'will', 'would', 'could', 'should'])
            keywords = [w for w in set(words) if len(w) > 4 and w not in common_words][:5]
            keyword_str = ', '.join(keywords) if keywords else topic.lower()
        except:
            keyword_str = topic.lower()

        return EpisodeMetadata(
            title=f"{topic} Digest - {digest_date.strftime('%b %d, %Y')}",
            summary=f"Today's essential {topic.lower()} insights and developments in a quick, digestible format.",
            keywords=keyword_str,
            category="Technology" if "tech" in topic.lower() or "ai" in topic.lower() else "Society"
        )

    def _generate_fallback_metadata(self, script_path: str, topic: str,
                                  digest_date: date) -> EpisodeMetadata:
        """Generate basic metadata when AI model fails (legacy file-based)"""
        logger.info("Using fallback metadata generation (file-based)")

        # Extract content from file and use content-based fallback
        try:
            content = self._extract_script_content(script_path)
            return self._generate_fallback_metadata_from_content(content, topic, digest_date)
        except:
            # If file read fails, use minimal fallback
            keyword_str = topic.lower()

        return EpisodeMetadata(
            title=f"{topic} Digest - {digest_date.strftime('%b %d, %Y')}",
            summary=f"Today's essential {topic.lower()} insights and developments in a quick, digestible format.",
            keywords=keyword_str,
            category="Technology" if "tech" in topic.lower() or "ai" in topic.lower() else "Society"
        )
    
    def generate_metadata_for_digest(self, digest, script_path: str = None) -> EpisodeMetadata:
        """Generate metadata for a digest object using database content"""

        # Use script content from database (database-first architecture)
        if not digest.script_content:
            raise MetadataGenerationError(f"No script content in database for digest {digest.id}")

        # Call the new method that accepts content directly
        return self.generate_metadata_from_content(
            script_content=digest.script_content,
            topic=digest.topic,
            digest_date=digest.digest_date
        )
    
    def update_digest_metadata(self, digest_repo, digest_id: int, metadata: EpisodeMetadata) -> None:
        """Update digest record with generated metadata"""
        
        # Update digest with title and summary
        # Note: This updates the existing update_audio method to include title and summary
        try:
            digest_repo.update_audio(
                digest_id=digest_id,
                mp3_path=None,  # Don't update MP3 path
                duration_seconds=0,  # Don't update duration
                title=metadata.title,
                summary=metadata.summary
            )
            logger.info(f"Updated digest {digest_id} with metadata")
        except Exception as e:
            logger.error(f"Failed to update digest {digest_id} metadata: {e}")
            raise MetadataGenerationError(f"Database update failed: {e}")
    
    def generate_rss_description(self, metadata: EpisodeMetadata, 
                                audio_duration_seconds: int = None) -> str:
        """Generate RSS feed description from metadata"""
        
        description_parts = [metadata.summary]
        
        if metadata.keywords:
            description_parts.append(f"\n\nTopics covered: {metadata.keywords}")
        
        if audio_duration_seconds and audio_duration_seconds > 0:
            duration_minutes = audio_duration_seconds // 60
            duration_seconds = audio_duration_seconds % 60
            description_parts.append(f"\n\nDuration: {duration_minutes}:{duration_seconds:02d}")
        
        if metadata.category:
            description_parts.append(f"\nCategory: {metadata.category}")
        
        return "".join(description_parts)