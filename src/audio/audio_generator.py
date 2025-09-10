"""
Audio Generator for RSS Podcast Transcript Digest System.
Converts digest scripts to high-quality audio using ElevenLabs TTS.
"""

import os
import json
import logging
import time
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import requests
from dataclasses import dataclass
from dotenv import load_dotenv

from .voice_manager import VoiceManager, VoiceSettings
from ..database.models import Digest, get_digest_repo
from ..config.config_manager import ConfigManager

logger = logging.getLogger(__name__)

@dataclass
class AudioMetadata:
    """Audio generation metadata"""
    file_path: str
    duration_seconds: Optional[float] = None
    file_size_bytes: Optional[int] = None
    voice_name: str = ""
    voice_id: str = ""
    generation_timestamp: Optional[datetime] = None

class AudioGenerationError(Exception):
    """Raised when audio generation fails"""
    pass

class AudioGenerator:
    """
    Generates high-quality audio from digest scripts using ElevenLabs TTS.
    Handles voice mapping, rate limiting, and file management.
    """
    
    def __init__(self, config_manager: ConfigManager = None):
        self.config = config_manager or ConfigManager()
        self.voice_manager = VoiceManager()
        self.digest_repo = get_digest_repo()
        
        # Setup output directory
        self.audio_dir = Path("data/completed-tts")
        self.audio_dir.mkdir(exist_ok=True)
        
        # ElevenLabs API configuration (lazy loading to handle dotenv timing)
        self.api_key = None
        self._api_key_checked = False
        
        self.base_url = "https://api.elevenlabs.io/v1"
        
        # Rate limiting settings
        self.request_delay = 1.0  # seconds between requests
        self.last_request_time = 0
    
    def _ensure_api_key(self):
        """Ensure API key is loaded (lazy initialization for dotenv timing)"""
        if not self._api_key_checked:
            # Explicitly load .env file to ensure variables are available
            load_dotenv()
            self.api_key = os.getenv('ELEVENLABS_API_KEY')
            if not self.api_key:
                raise ValueError("ELEVENLABS_API_KEY environment variable is required")
            
            # Set up headers now that we have the API key
            self.headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key
            }
            self._api_key_checked = True
            logger.info("ElevenLabs API key initialized successfully")
        
    def _rate_limit_delay(self):
        """Enforce rate limiting between API requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            delay = self.request_delay - elapsed
            logger.info(f"Rate limiting: waiting {delay:.1f} seconds")
            time.sleep(delay)
        self.last_request_time = time.time()
    
    def _clean_script_for_tts(self, script_content: str) -> str:
        """Clean script content for optimal TTS conversion"""
        lines = script_content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Skip markdown headers, metadata, and formatting
            if line.strip().startswith('#'):
                continue
            if line.strip().startswith('*') and line.strip().endswith('*'):
                continue
            if line.strip().startswith('---'):
                continue
            if not line.strip():
                continue
                
            # Clean up the line
            cleaned_line = line.strip()
            
            # Remove markdown formatting
            cleaned_line = cleaned_line.replace('**', '')
            cleaned_line = cleaned_line.replace('*', '')
            cleaned_line = cleaned_line.replace('`', '')
            
            # Ensure proper sentence ending
            if cleaned_line and not cleaned_line.endswith(('.', '!', '?')):
                cleaned_line += '.'
            
            cleaned_lines.append(cleaned_line)
        
        # Join with proper spacing and add pauses
        text = ' '.join(cleaned_lines)
        
        # Add natural pauses for better flow
        text = text.replace('. ', '. ... ')  # Pause after sentences
        text = text.replace('! ', '! ... ')  # Pause after exclamations
        text = text.replace('? ', '? ... ')  # Pause after questions
        
        # Limit text length for API (ElevenLabs has limits)
        max_chars = 5000  # Conservative limit
        if len(text) > max_chars:
            # Find a good breaking point
            text = text[:max_chars]
            last_sentence = max(text.rfind('. '), text.rfind('! '), text.rfind('? '))
            if last_sentence > max_chars * 0.8:  # If we can find a sentence ending
                text = text[:last_sentence + 1]
            logger.warning(f"Script truncated to {len(text)} characters for TTS")
        
        return text
    
    def generate_audio_for_script(self, script_path: str, topic: str) -> AudioMetadata:
        """Generate audio from a script file"""
        logger.info(f"Generating audio for script: {script_path}")
        
        # Read script content
        script_file = Path(script_path)
        if not script_file.exists():
            raise AudioGenerationError(f"Script file not found: {script_path}")
        
        with open(script_file, 'r', encoding='utf-8') as f:
            script_content = f.read()
        
        # Clean script for TTS
        tts_text = self._clean_script_for_tts(script_content)
        logger.info(f"Cleaned script: {len(tts_text)} characters for TTS")
        
        # Get voice configuration for topic
        voice_id = self._get_voice_id_for_topic(topic)
        voice_settings = self.voice_manager.get_voice_settings_for_topic(topic)
        
        logger.info(f"Using voice {voice_id} for topic '{topic}'")
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_topic = topic.replace(' ', '_').replace('&', 'and')
        filename = f"{safe_topic}_{timestamp}.mp3"
        output_path = self.audio_dir / filename
        
        # Generate audio via ElevenLabs API
        audio_data = self._generate_tts_audio(tts_text, voice_id, voice_settings)
        
        # Save audio file
        with open(output_path, 'wb') as f:
            f.write(audio_data)
        
        # Get file metadata
        file_size = output_path.stat().st_size
        
        # Estimate duration (rough approximation: ~150 words per minute, ~5 chars per word)
        estimated_duration = (len(tts_text) / 5) / 150 * 60  # seconds
        
        # Get voice name
        voice = self.voice_manager.get_voice_by_id(voice_id)
        voice_name = voice.name if voice else "Unknown"
        
        logger.info(f"Generated audio: {output_path} ({file_size} bytes, ~{estimated_duration:.1f}s)")
        
        return AudioMetadata(
            file_path=str(output_path),
            duration_seconds=estimated_duration,
            file_size_bytes=file_size,
            voice_name=voice_name,
            voice_id=voice_id,
            generation_timestamp=datetime.now()
        )
    
    def _get_voice_id_for_topic(self, topic: str) -> str:
        """Get voice ID for a specific topic"""
        try:
            with open("config/topics.json", 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            for topic_config in config.get('topics', []):
                if topic_config['name'] == topic:
                    return topic_config['voice_id']
            
            raise AudioGenerationError(f"No voice configuration found for topic: {topic}")
            
        except Exception as e:
            raise AudioGenerationError(f"Failed to get voice ID for topic '{topic}': {e}")
    
    def _generate_tts_audio(self, text: str, voice_id: str, voice_settings: VoiceSettings) -> bytes:
        """Generate TTS audio using ElevenLabs API"""
        
        # Ensure API key is loaded
        self._ensure_api_key()
        
        # Enforce rate limiting
        self._rate_limit_delay()
        
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",  # High quality model
            "voice_settings": {
                "stability": voice_settings.stability,
                "similarity_boost": voice_settings.similarity_boost,
                "style": voice_settings.style,
                "use_speaker_boost": voice_settings.use_speaker_boost
            }
        }
        
        logger.info(f"Sending TTS request: {len(text)} chars, voice {voice_id}")
        
        # Retry logic for transient failures
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt}/{max_retries}")
                    time.sleep(5)  # Wait 5 seconds before retry
                
                response = requests.post(
                    url,
                    json=payload,
                    headers=self.headers,
                    timeout=120,  # Increased timeout for longer scripts
                    stream=False  # Ensure we get full response, not streaming
                )
                response.raise_for_status()
                
                # Verify we have audio content
                if not response.content:
                    raise AudioGenerationError("Received empty response from ElevenLabs API")
                
                # Check content type
                content_type = response.headers.get('content-type', '')
                if 'audio' not in content_type.lower():
                    logger.warning(f"Unexpected content-type: {content_type}")
                    # Log first 200 chars of response for debugging
                    logger.warning(f"Response preview: {str(response.content[:200])}")
                
                logger.info(f"TTS generation successful: {len(response.content)} bytes, content-type: {content_type}")
                return response.content
                
            except requests.exceptions.Timeout as e:
                if attempt < max_retries:
                    logger.warning(f"TTS request timed out (attempt {attempt + 1}/{max_retries + 1}), retrying...")
                    continue
                else:
                    logger.error(f"TTS request failed after {max_retries + 1} attempts: timeout")
                    raise AudioGenerationError(f"TTS generation timed out after {max_retries + 1} attempts")
                    
            except requests.RequestException as e:
                if attempt < max_retries:
                    logger.warning(f"TTS request failed (attempt {attempt + 1}/{max_retries + 1}), retrying...")
                    continue
                else:
                    logger.error(f"ElevenLabs API request failed: {e}")
                    if hasattr(e, 'response') and e.response is not None:
                        try:
                            error_detail = e.response.json()
                            logger.error(f"API error details: {error_detail}")
                        except:
                            logger.error(f"API response: {e.response.text}")
                    raise AudioGenerationError(f"TTS generation failed: {e}")
    
    def generate_audio_for_digest(self, digest: Digest) -> AudioMetadata:
        """Generate audio for a digest record"""
        if not digest.script_path:
            raise AudioGenerationError(f"Digest {digest.id} has no script path")
        
        logger.info(f"Generating audio for digest {digest.id}: {digest.topic}")
        
        # Generate audio
        audio_metadata = self.generate_audio_for_script(digest.script_path, digest.topic)
        
        # Update digest record with audio information
        self.digest_repo.update_audio(
            digest.id,
            audio_metadata.file_path,
            int(audio_metadata.duration_seconds) if audio_metadata.duration_seconds else 0,
            title="",  # Will be generated in next task
            summary=""  # Will be generated in next task
        )
        
        logger.info(f"Updated digest {digest.id} with audio metadata")
        
        return audio_metadata
    
    def generate_audio_for_date(self, target_date: date) -> List[AudioMetadata]:
        """Generate audio for all digests on a specific date"""
        logger.info(f"Generating audio for digests on {target_date}")
        
        # Get digests for the date
        digests = self.digest_repo.get_by_date(target_date)
        
        if not digests:
            logger.warning(f"No digests found for {target_date}")
            return []
        
        logger.info(f"Found {len(digests)} digests to process")
        
        audio_metadata_list = []
        
        for digest in digests:
            try:
                # Skip if audio already exists
                if digest.mp3_path and Path(digest.mp3_path).exists():
                    logger.info(f"Audio already exists for digest {digest.id}: {digest.mp3_path}")
                    continue
                
                audio_metadata = self.generate_audio_for_digest(digest)
                audio_metadata_list.append(audio_metadata)
                
                # Brief pause between generations
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Failed to generate audio for digest {digest.id}: {e}")
                continue
        
        logger.info(f"Generated {len(audio_metadata_list)} audio files for {target_date}")
        return audio_metadata_list
    
    def list_generated_audio(self) -> List[Dict[str, any]]:
        """List all generated audio files with metadata"""
        audio_files = []
        
        for audio_file in self.audio_dir.glob("*.mp3"):
            stat = audio_file.stat()
            audio_files.append({
                'filename': audio_file.name,
                'path': str(audio_file),
                'size_bytes': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime),
                'modified': datetime.fromtimestamp(stat.st_mtime)
            })
        
        # Sort by creation time, newest first
        audio_files.sort(key=lambda x: x['created'], reverse=True)
        return audio_files