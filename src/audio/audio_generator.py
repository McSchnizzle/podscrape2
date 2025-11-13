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
from .dialogue_chunker import chunk_dialogue_script, DialogueChunk
from ..database.models import Digest, get_digest_repo, get_topic_repo
from ..config.config_manager import ConfigManager
from ..config.web_config import WebConfigManager
from ..utils.timezone import get_pacific_now

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
    
    def __init__(self, config_manager: ConfigManager = None, web_config: WebConfigManager = None):
        self.config = config_manager or ConfigManager()
        self.web_config = web_config or self._safe_create_web_config()
        self.voice_manager = VoiceManager()
        self.digest_repo = get_digest_repo()

        # Load AI configuration for TTS generation
        if self.web_config:
            self.ai_model = self.web_config.get_setting("ai_tts_generation", "model", "eleven_turbo_v2_5")
            self.max_characters = self.web_config.get_setting("ai_tts_generation", "max_characters", 35000)

            # Validate character limits against model capabilities
            self.max_characters = self._validate_and_adjust_char_limit(self.ai_model, self.max_characters)
        else:
            self.ai_model = "eleven_turbo_v2_5"
            self.max_characters = 35000
        
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
            logger.info(f"ElevenLabs API key initialized successfully with model: {self.ai_model}, max_characters: {self.max_characters}")

    def _safe_create_web_config(self) -> Optional[WebConfigManager]:
        """Safely create web config, return None if not available"""
        try:
            return WebConfigManager()
        except Exception:
            return None

    def _validate_and_adjust_char_limit(self, model: str, requested_chars: int) -> int:
        """Validate and adjust character limit based on model capabilities"""
        if not self.web_config:
            return requested_chars

        # Get model's maximum character limit
        max_limit = self.web_config.get_model_limit('elevenlabs', model, 'max_characters')
        if max_limit > 0 and requested_chars > max_limit:
            logger.warning(f"Requested {requested_chars} characters exceeds {model} limit of {max_limit}, adjusting to {max_limit}")
            return max_limit

        return requested_chars
        
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
        
        # Limit text length for API using configured character limit
        if len(text) > self.max_characters:
            # Find a good breaking point
            text = text[:self.max_characters]
            last_sentence = max(text.rfind('. '), text.rfind('! '), text.rfind('? '))
            if last_sentence > self.max_characters * 0.8:  # If we can find a sentence ending
                text = text[:last_sentence + 1]
            logger.warning(f"Script truncated to {len(text)} characters for TTS (limit: {self.max_characters})")
        
        return text
    
    def generate_audio_for_script(self, script_content: str, topic: str, timestamp: str = None, script_reference: str = None, episode_id: int = None) -> AudioMetadata:
        """Generate audio from script content - routes to dialogue or single-voice based on topic config"""
        ref_info = f" (ref: {script_reference})" if script_reference else ""
        logger.info(f"Generating audio for script content{ref_info}")

        if not script_content or not script_content.strip():
            raise AudioGenerationError(f"Script content is empty{ref_info}")

        # Get topic configuration to determine generation mode
        topic_config = self._get_topic_config(topic)

        # Generate filename (allow caller to supply an exact timestamp to match script)
        if not timestamp:
            timestamp = get_pacific_now().strftime('%Y%m%d_%H%M%S')
        safe_topic = topic.replace(' ', '_').replace('&', 'and')
        # Include episode ID in filename if provided
        if episode_id:
            filename = f"{safe_topic}_ep{episode_id}_{timestamp}.mp3"
        else:
            filename = f"{safe_topic}_{timestamp}.mp3"
        output_path = self.audio_dir / filename

        # CRITICAL FIX: Check use_dialogue_api to route to correct TTS method
        if topic_config and topic_config.use_dialogue_api and topic_config.voice_config:
            logger.info(f"🎭 DIALOGUE MODE for '{topic}' - using Text-to-Dialogue API with chunking")
            # Call existing chunked dialogue method with correct signature
            return self._generate_chunked_dialogue_audio(
                script_content=script_content,  # DON'T clean - preserves SPEAKER_1/SPEAKER_2 and audio tags
                topic=topic,
                voice_config=topic_config.voice_config,
                dialogue_model=topic_config.dialogue_model,
                timestamp=timestamp,
                episode_id=episode_id
            )
        else:
            logger.info(f"📢 SINGLE-VOICE MODE for '{topic}' - using standard TTS API")
            # Clean script for single-voice TTS
            tts_text = self._clean_script_for_tts(script_content)
            logger.info(f"Cleaned script: {len(tts_text)} characters for TTS")

            # Get voice configuration for topic
            voice_id = self._get_voice_id_for_topic(topic)
            voice_settings = self.voice_manager.get_voice_settings_for_topic(topic)

            logger.info(f"Using voice {voice_id} for topic '{topic}'")

            # Check if we need to chunk for v3 model (3000 char limit)
            needs_chunking = (
                topic_config and
                topic_config.dialogue_model == 'eleven_v3' and
                len(tts_text) > 3000
            )

            if needs_chunking:
                logger.info(f"Script exceeds 3000 chars ({len(tts_text)}), chunking for {topic_config.dialogue_model} model")
                audio_data = self._generate_chunked_narrative_audio(
                    tts_text,
                    voice_id,
                    voice_settings,
                    output_path,
                    model_id=topic_config.dialogue_model  # Pass per-topic model
                )
                file_size = output_path.stat().st_size
            else:
                # Generate audio via ElevenLabs API (single request)
                audio_data = self._generate_tts_audio(tts_text, voice_id, voice_settings)

                # Save audio file
                with open(output_path, 'wb') as f:
                    f.write(audio_data)

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
                generation_timestamp=get_pacific_now()
            )
    
    def _get_topic_config(self, topic: str):
        """Get topic configuration from database"""
        try:
            from src.database.models import get_topic_repo
            topic_repo = get_topic_repo()
            all_topics = topic_repo.get_all_topics()
            return next((t for t in all_topics if t.name == topic), None)
        except Exception as e:
            logger.warning(f"Failed to get topic config for '{topic}': {e}")
            return None

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

    def _generate_chunked_narrative_audio(
        self,
        text: str,
        voice_id: str,
        voice_settings: VoiceSettings,
        output_path: Path,
        model_id: str = None
    ) -> bytes:
        """
        Generate audio for long narrative scripts by chunking and concatenating.

        For eleven_v3 model with scripts >3000 chars:
        1. Split text at sentence boundaries into ~2800 char chunks
        2. Generate audio for each chunk via TTS API
        3. Concatenate chunks using ffmpeg

        Args:
            text: Full narrative text (already cleaned for TTS)
            voice_id: ElevenLabs voice ID
            voice_settings: Voice configuration
            output_path: Final MP3 output path
            model_id: Optional model ID (uses per-topic model if provided)

        Returns:
            Audio bytes (from concatenated file)
        """
        import tempfile
        import shutil

        MAX_CHUNK_SIZE = 2800  # Safety margin under v3's 3000 char limit

        logger.info(f"Chunking narrative script: {len(text)} chars")

        # Split text into chunks at sentence boundaries
        chunks = self._chunk_narrative_text(text, MAX_CHUNK_SIZE)
        logger.info(f"Split into {len(chunks)} chunks")

        # Create temp directory for chunk files
        temp_dir = Path(tempfile.mkdtemp(prefix="narrative_chunks_"))

        try:
            chunk_files = []

            # Generate audio for each chunk
            for i, chunk_text in enumerate(chunks, 1):
                chunk_file = temp_dir / f"chunk_{i:03d}.mp3"
                logger.info(f"Processing chunk {i}/{len(chunks)} ({len(chunk_text)} chars)")

                # Generate audio for this chunk (use per-topic model if provided)
                audio_bytes = self._generate_tts_audio(chunk_text, voice_id, voice_settings, model_id=model_id)

                # Save chunk to temp file
                with open(chunk_file, 'wb') as f:
                    f.write(audio_bytes)

                chunk_files.append(chunk_file)
                logger.info(f"Saved chunk {i} to {chunk_file} ({len(audio_bytes)} bytes)")

            # Concatenate all chunks
            self._concatenate_audio_chunks(chunk_files, output_path)

            logger.info(f"Generated chunked narrative audio: {output_path} ({len(chunks)} chunks)")

            # Return empty bytes since we saved directly to output_path
            return b''

        finally:
            # Clean up temp directory
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory {temp_dir}: {e}")

    def _chunk_narrative_text(self, text: str, max_chunk_size: int) -> list[str]:
        """
        Split narrative text into chunks at sentence boundaries.

        Args:
            text: Full narrative text
            max_chunk_size: Maximum characters per chunk

        Returns:
            List of text chunks
        """
        import re

        # Split into sentences (preserve punctuation)
        sentences = re.split(r'([.!?]+\s+)', text)

        chunks = []
        current_chunk = ""

        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            punctuation = sentences[i + 1] if i + 1 < len(sentences) else ""
            full_sentence = sentence + punctuation

            if len(current_chunk) + len(full_sentence) > max_chunk_size and current_chunk:
                # Save current chunk and start new one
                chunks.append(current_chunk.strip())
                current_chunk = full_sentence
            else:
                current_chunk += full_sentence

        # Add final chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _generate_tts_audio(self, text: str, voice_id: str, voice_settings: VoiceSettings, model_id: str = None) -> bytes:
        """Generate TTS audio using ElevenLabs API"""

        # Ensure API key is loaded
        self._ensure_api_key()

        # Enforce rate limiting
        self._rate_limit_delay()

        url = f"{self.base_url}/text-to-speech/{voice_id}"

        # Use per-topic model if provided, otherwise use global default
        effective_model = model_id if model_id else self.ai_model

        # For eleven_v3 model, normalize stability to allowed values: 0.0, 0.5, 1.0
        stability = voice_settings.stability
        if effective_model == "eleven_v3":
            if stability < 0.25:
                stability = 0.0
            elif stability < 0.75:
                stability = 0.5
            else:
                stability = 1.0

        payload = {
            "text": text,
            "model_id": effective_model,  # Use per-topic model if provided
            "voice_settings": {
                "stability": stability,  # Normalized for v3 if needed
                "similarity_boost": voice_settings.similarity_boost,
                "style": voice_settings.style,
                "use_speaker_boost": voice_settings.use_speaker_boost
            }
        }
        
        logger.info(f"Sending TTS request: {len(text)} chars, voice {voice_id}, model {effective_model}")
        
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

    def _parse_dialogue_script(self, script: str, voice_config: dict) -> List[dict]:
        """
        Parse dialogue script into ElevenLabs Text-to-Dialogue API format.

        Args:
            script: Dialogue script with SPEAKER_1/SPEAKER_2 labels
            voice_config: Dict mapping speaker names to voice IDs

        Returns:
            List of dialogue inputs: [{"speaker": "voice_id", "text": "..."}]
        """
        import re

        # Extract speaker-to-voice mapping from voice_config
        # voice_config format: {"speaker_1": {"voice_id": "...", "role": "..."}, "speaker_2": {...}}
        # or {"SPEAKER_1": {"voice_id": "...", "role": "..."}, "SPEAKER_2": {...}}
        speaker_to_voice = {}
        for speaker_name, config in voice_config.items():
            if isinstance(config, dict) and 'voice_id' in config:
                # Normalize to uppercase SPEAKER_1, SPEAKER_2 format
                normalized_name = speaker_name.upper().replace('_', '_')
                if not normalized_name.startswith('SPEAKER_'):
                    normalized_name = f'SPEAKER_{normalized_name.split("_")[-1]}'
                speaker_to_voice[normalized_name] = config['voice_id']
            else:
                logger.warning(f"Invalid voice config for {speaker_name}: {config}")

        if not speaker_to_voice:
            raise AudioGenerationError("No speaker-to-voice mappings found in voice_config")

        logger.info(f"Speaker-to-voice mappings: {speaker_to_voice}")

        # Parse dialogue script into individual turns
        # Pattern matches: "SPEAKER_1:", "SPEAKER_2:", "SPEAKER_1 (Young Jamal):", etc.
        dialogue_inputs = []
        # Use \Z for end of string (not $ which matches end of line in MULTILINE mode)
        pattern = re.compile(r'^(SPEAKER_[12])(?:\s*\([^)]+\))?:\s*(.+?)(?=^SPEAKER_[12](?:\s*\([^)]+\))?:|\Z)', re.MULTILINE | re.DOTALL)

        for match in pattern.finditer(script):
            speaker_name = match.group(1)
            text = match.group(2).strip()

            # Map speaker name to voice ID
            voice_id = speaker_to_voice.get(speaker_name)
            if not voice_id:
                logger.warning(f"No voice ID found for {speaker_name}, skipping turn")
                continue

            dialogue_inputs.append({
                "voice_id": voice_id,  # API expects "voice_id" not "speaker"
                "text": text
            })

        logger.info(f"Parsed {len(dialogue_inputs)} dialogue turns from script")
        return dialogue_inputs

    def _call_text_to_dialogue_api(self, dialogue_inputs: List[dict], model_id: str = "eleven_v3") -> bytes:
        """
        Call ElevenLabs Text-to-Dialogue API with retry logic.

        Args:
            dialogue_inputs: List of {"speaker": "voice_id", "text": "..."}
            model_id: ElevenLabs model ID (default: eleven_v3)

        Returns:
            Audio bytes (MP3 format)

        Raises:
            AudioGenerationError: If API call fails after retries
        """
        # Ensure API key is loaded
        self._ensure_api_key()

        # Enforce rate limiting
        self._rate_limit_delay()

        url = f"{self.base_url}/text-to-dialogue"

        payload = {
            "model_id": model_id,
            "inputs": dialogue_inputs  # API expects "inputs" not "dialogue_inputs"
        }

        total_chars = sum(len(d['text']) for d in dialogue_inputs)
        logger.info(f"Calling Text-to-Dialogue API: {len(dialogue_inputs)} turns, {total_chars} chars, model {model_id}")

        # Retry logic with exponential backoff
        max_retries = 3
        base_delay = 5  # seconds

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    delay = base_delay * (2 ** (attempt - 1))  # Exponential backoff
                    logger.info(f"Retry attempt {attempt}/{max_retries} after {delay}s delay")
                    time.sleep(delay)

                response = requests.post(
                    url,
                    json=payload,
                    headers=self.headers,
                    timeout=180,  # 3 minutes for dialogue generation
                    stream=False
                )
                response.raise_for_status()

                # Verify we have audio content
                if not response.content:
                    raise AudioGenerationError("Received empty response from Text-to-Dialogue API")

                # Check content type
                content_type = response.headers.get('content-type', '')
                if 'audio' not in content_type.lower():
                    logger.warning(f"Unexpected content-type: {content_type}")
                    logger.warning(f"Response preview: {str(response.content[:200])}")

                logger.info(f"Text-to-Dialogue generation successful: {len(response.content)} bytes")
                return response.content

            except requests.exceptions.Timeout as e:
                if attempt < max_retries:
                    logger.warning(f"Text-to-Dialogue request timed out (attempt {attempt + 1}/{max_retries + 1}), retrying...")
                    continue
                else:
                    logger.error(f"Text-to-Dialogue request failed after {max_retries + 1} attempts: timeout")
                    raise AudioGenerationError(f"Text-to-Dialogue generation timed out after {max_retries + 1} attempts")

            except requests.RequestException as e:
                if attempt < max_retries:
                    logger.warning(f"Text-to-Dialogue request failed (attempt {attempt + 1}/{max_retries + 1}), retrying...")
                    continue
                else:
                    logger.error(f"ElevenLabs Text-to-Dialogue API request failed: {e}")
                    if hasattr(e, 'response') and e.response is not None:
                        try:
                            error_detail = e.response.json()
                            logger.error(f"API error details: {error_detail}")
                        except:
                            logger.error(f"API response: {e.response.text}")
                    raise AudioGenerationError(f"Text-to-Dialogue generation failed: {e}")

    def _concatenate_audio_chunks(self, chunk_files: List[Path], output_path: Path) -> Path:
        """
        Concatenate multiple MP3 files using ffmpeg concat demuxer.

        Args:
            chunk_files: List of MP3 file paths to concatenate
            output_path: Path for final concatenated MP3

        Returns:
            Path to concatenated MP3 file

        Raises:
            AudioGenerationError: If concatenation fails
        """
        import subprocess
        import tempfile

        if not chunk_files:
            raise AudioGenerationError("No chunk files to concatenate")

        if len(chunk_files) == 1:
            # No concatenation needed, just copy/rename
            import shutil
            shutil.copy(chunk_files[0], output_path)
            logger.info(f"Single chunk, copied to {output_path}")
            return output_path

        # Create concat file list for ffmpeg
        # Format: file '/path/to/chunk1.mp3'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as concat_file:
            concat_file_path = concat_file.name
            for chunk_path in chunk_files:
                # Use absolute paths and escape quotes
                abs_path = str(chunk_path.resolve())
                concat_file.write(f"file '{abs_path}'\n")

        logger.info(f"Concatenating {len(chunk_files)} audio chunks using ffmpeg")

        try:
            # Use ffmpeg concat demuxer for seamless concatenation
            # -f concat: concat demuxer
            # -safe 0: allow absolute paths
            # -i: input concat file list
            # -c copy: copy codec (no re-encoding for speed)
            cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file_path,
                '-c', 'copy',
                '-y',  # Overwrite output file if exists
                str(output_path)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes max
            )

            if result.returncode != 0:
                logger.error(f"ffmpeg concatenation failed: {result.stderr}")
                raise AudioGenerationError(f"ffmpeg concatenation failed: {result.stderr}")

            # Verify output file was created
            if not output_path.exists():
                raise AudioGenerationError(f"Concatenated file not created: {output_path}")

            file_size = output_path.stat().st_size
            logger.info(f"Successfully concatenated {len(chunk_files)} chunks → {output_path} ({file_size} bytes)")

            return output_path

        except subprocess.TimeoutExpired:
            logger.error("ffmpeg concatenation timed out after 5 minutes")
            raise AudioGenerationError("Audio concatenation timed out")

        except Exception as e:
            logger.error(f"Audio concatenation failed: {e}")
            raise AudioGenerationError(f"Audio concatenation failed: {e}")

        finally:
            # Clean up concat file list
            try:
                Path(concat_file_path).unlink()
            except Exception as e:
                logger.warning(f"Failed to delete concat file: {e}")

    def _generate_chunked_dialogue_audio(
        self,
        script_content: str,
        topic: str,
        voice_config: dict,
        dialogue_model: str,
        timestamp: str = None,
        episode_id: int = None
    ) -> AudioMetadata:
        """
        Generate multi-voice dialogue audio with chunking support.

        Process:
        1. Use script content from database
        2. Chunk script into segments that fit within API limits
        3. Generate audio for each chunk via Text-to-Dialogue API
        4. Concatenate chunks into final MP3
        5. Clean up intermediate files

        Args:
            script_content: Dialogue script content (not file path)
            topic: Topic name (for output filename)
            voice_config: Speaker-to-voice mapping
            dialogue_model: ElevenLabs model ID (e.g., "eleven_v3")
            timestamp: Optional timestamp for filename consistency

        Returns:
            AudioMetadata with final MP3 path

        Raises:
            AudioGenerationError: If any step fails
        """
        import tempfile
        import shutil

        logger.info(f"Generating chunked dialogue audio for {topic}")
        logger.info(f"Voice config: {voice_config}")
        logger.info(f"Dialogue model: {dialogue_model}")

        # Chunk the dialogue script
        # Use 2500 chars for safety margin (API limit is 3000)
        try:
            chunks = chunk_dialogue_script(script_content, max_chunk_size=2500)
            logger.info(f"Split script into {len(chunks)} chunks")
            for chunk in chunks:
                logger.info(f"  Chunk {chunk.chunk_number}: {chunk.char_count} chars, {chunk.turn_count} turns")
        except Exception as e:
            raise AudioGenerationError(f"Failed to chunk dialogue script: {e}")

        # Create temp directory for chunk files
        temp_dir = Path(tempfile.mkdtemp(prefix='dialogue_chunks_'))
        logger.info(f"Created temp directory: {temp_dir}")

        # Progress tracking for error recovery
        progress_file = temp_dir / "progress.json"
        completed_chunks = set()

        # Load existing progress if available (retry scenario)
        if progress_file.exists():
            try:
                with open(progress_file, 'r') as f:
                    progress_data = json.load(f)
                    completed_chunks = set(progress_data.get('completed_chunks', []))
                    logger.info(f"Loaded progress: {len(completed_chunks)} chunks already completed")
            except Exception as e:
                logger.warning(f"Failed to load progress file: {e}")

        chunk_files = []

        try:
            # Generate audio for each chunk
            for chunk in chunks:
                chunk_file = temp_dir / f"chunk_{chunk.chunk_number:03d}.mp3"

                # Skip if already completed (error recovery)
                if chunk.chunk_number in completed_chunks:
                    logger.info(f"Chunk {chunk.chunk_number}/{len(chunks)} already completed, skipping")
                    chunk_files.append(chunk_file)
                    continue

                logger.info(f"Processing chunk {chunk.chunk_number}/{len(chunks)}")

                # Parse chunk into dialogue inputs
                dialogue_inputs = self._parse_dialogue_script(chunk.text, voice_config)

                # Call Text-to-Dialogue API
                audio_bytes = self._call_text_to_dialogue_api(dialogue_inputs, model_id=dialogue_model)

                # Save chunk to temp file
                with open(chunk_file, 'wb') as f:
                    f.write(audio_bytes)

                chunk_files.append(chunk_file)
                logger.info(f"Saved chunk {chunk.chunk_number} to {chunk_file} ({len(audio_bytes)} bytes)")

                # Update progress tracking
                completed_chunks.add(chunk.chunk_number)
                try:
                    with open(progress_file, 'w') as f:
                        json.dump({'completed_chunks': sorted(list(completed_chunks))}, f)
                except Exception as e:
                    logger.warning(f"Failed to update progress file: {e}")

            # Generate output filename
            if not timestamp:
                timestamp = get_pacific_now().strftime('%Y%m%d_%H%M%S')
            safe_topic = topic.replace(' ', '_').replace('&', 'and')
            # Include episode ID in filename if provided
            if episode_id:
                filename = f"{safe_topic}_ep{episode_id}_{timestamp}.mp3"
            else:
                filename = f"{safe_topic}_{timestamp}.mp3"
            output_path = self.audio_dir / filename

            # Concatenate all chunks
            self._concatenate_audio_chunks(chunk_files, output_path)

            # Get file metadata
            file_size = output_path.stat().st_size

            # Estimate duration based on total script characters
            total_chars = sum(chunk.char_count for chunk in chunks)
            estimated_duration = (total_chars / 5) / 150 * 60  # seconds

            logger.info(f"Generated dialogue audio: {output_path} ({file_size} bytes, ~{estimated_duration:.1f}s)")

            return AudioMetadata(
                file_path=str(output_path),
                duration_seconds=estimated_duration,
                file_size_bytes=file_size,
                voice_name=f"Multi-voice ({len(voice_config)} speakers)",
                voice_id="dialogue",
                generation_timestamp=get_pacific_now()
            )

        finally:
            # Clean up temp directory and chunk files
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temp directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory {temp_dir}: {e}")

    def generate_audio_for_digest(self, digest: Digest) -> AudioMetadata:
        """
        Generate audio for a digest record.

        Routes to either:
        - Dialogue mode: Multi-voice Text-to-Dialogue API with chunking
        - Narrative mode: Single-voice TTS (existing behavior)

        Based on topic configuration (use_dialogue_api, dialogue_model, voice_config)
        """
        if not digest.script_path:
            raise AudioGenerationError(f"Digest {digest.id} has no script path")

        logger.info(f"Generating audio for digest {digest.id}: {digest.topic}")

        # Extract timestamp from script filename to keep MP3 in lockstep
        from pathlib import Path as _P
        import re as _re
        ts = None
        try:
            m = _re.search(r"_(\d{8}_\d{6})\.md$", str(_P(digest.script_path).name))
            if m:
                ts = m.group(1)
        except Exception:
            ts = None

        # Get topic configuration from database
        topic_repo = get_topic_repo()
        try:
            all_topics = topic_repo.get_all_topics()
            topic_config = next((t for t in all_topics if t.name == digest.topic), None)

            if not topic_config:
                logger.warning(f"No topic configuration found for '{digest.topic}', using narrative mode")
                use_dialogue_api = False
            else:
                use_dialogue_api = topic_config.use_dialogue_api
                dialogue_model = topic_config.dialogue_model or "eleven_v3"
                voice_config = topic_config.voice_config or {}

                logger.info(f"Topic configuration: use_dialogue_api={use_dialogue_api}, dialogue_model={dialogue_model}")
        except Exception as e:
            logger.warning(f"Failed to get topic configuration for '{digest.topic}': {e}, using narrative mode")
            use_dialogue_api = False

        # Route to appropriate generation method
        if use_dialogue_api:
            logger.info(f"Using DIALOGUE MODE for {digest.topic}")

            # Ensure we have script content
            if not digest.script_content:
                raise AudioGenerationError(f"Digest {digest.id} has no script_content")

            audio_metadata = self._generate_chunked_dialogue_audio(
                script_content=digest.script_content,
                topic=digest.topic,
                voice_config=voice_config,
                dialogue_model=dialogue_model,
                timestamp=ts,
                episode_id=digest.id
            )
        else:
            logger.info(f"Using NARRATIVE MODE for {digest.topic}")

            # Ensure we have script content
            if not digest.script_content:
                raise AudioGenerationError(f"Digest {digest.id} has no script_content")

            audio_metadata = self.generate_audio_for_script(
                script_content=digest.script_content,
                topic=digest.topic,
                timestamp=ts,
                episode_id=digest.id
            )

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
