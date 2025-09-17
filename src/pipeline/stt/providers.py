#!/usr/bin/env python3
"""
STT (Speech-to-Text) Provider Abstraction
Provides a unified interface for different transcription providers.
"""

import os
import json
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

try:
    from ...config.web_config import WebConfigManager
except ImportError:
    # Fallback in case WebConfigManager is not available
    WebConfigManager = None

# Self-contained error handling and logging to avoid import issues
class PodcastError(Exception):
    """Raised when podcast processing operations fail"""
    pass

def get_logger(name):
    """Simple logger factory"""
    return logging.getLogger(name)

def retry_with_backoff(max_retries=3, backoff_factor=2.0):
    """Simple retry decorator with exponential backoff"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries:
                        raise
                    wait_time = backoff_factor ** attempt
                    time.sleep(wait_time)
            return func(*args, **kwargs)
        return wrapper
    return decorator

@dataclass
class TranscriptionChunk:
    """Represents transcription of a single audio chunk"""
    chunk_number: int
    start_time_seconds: float
    end_time_seconds: float
    text: str
    confidence: float
    processing_time_seconds: float

@dataclass
class EpisodeTranscription:
    """Complete transcription of an episode"""
    episode_guid: str
    chunks: List[TranscriptionChunk]
    total_duration_seconds: float
    total_processing_time_seconds: float
    word_count: int
    chunk_count: int
    transcript_text: str
    generated_at: datetime

logger = get_logger(__name__)


class STTProvider(ABC):
    """
    Abstract base class for Speech-to-Text providers
    """

    def __init__(self, chunk_duration_minutes: int = 3):
        """
        Initialize STT provider

        Args:
            chunk_duration_minutes: Duration of audio chunks in minutes
        """
        self.chunk_duration_seconds = chunk_duration_minutes * 60
        self.provider_name = self.__class__.__name__.lower().replace('provider', '')

        logger.info(f"Initialized {self.provider_name} STT provider")

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the provider (load models, authenticate, etc.)

        Returns:
            True if initialization successful, False otherwise
        """
        pass

    @abstractmethod
    def transcribe_episode(self, audio_chunks: List[str], episode_guid: str) -> EpisodeTranscription:
        """
        Transcribe a complete episode from audio chunks

        Args:
            audio_chunks: List of paths to audio chunk files
            episode_guid: Unique episode identifier

        Returns:
            EpisodeTranscription object with complete transcription

        Raises:
            PodcastError: If transcription fails
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict:
        """
        Get information about the loaded model/provider

        Returns:
            Dict with provider information
        """
        pass

    def _combine_chunks(self, chunks: List[TranscriptionChunk]) -> str:
        """
        Combine transcription chunks into complete text
        Shared implementation for all providers
        """
        if not chunks:
            return ""

        # Simple concatenation with proper spacing
        text_parts = []
        for chunk in chunks:
            if chunk.text.strip():
                # Ensure proper sentence spacing
                text = chunk.text.strip()
                if text and not text.endswith(('.', '!', '?')):
                    # Add space if the chunk doesn't end with punctuation
                    # and there's more content coming
                    if chunk != chunks[-1]:
                        text += " "
                text_parts.append(text)

        full_text = " ".join(text_parts)

        # Clean up any double spaces
        while "  " in full_text:
            full_text = full_text.replace("  ", " ")

        return full_text.strip()

    def save_transcription(self, transcription: EpisodeTranscription,
                          output_dir: str) -> Tuple[str, str]:
        """
        Save transcription to both JSON and TXT formats

        Args:
            transcription: Episode transcription to save
            output_dir: Directory to save files

        Returns:
            Tuple of (json_path, txt_path)
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = transcription.generated_at.strftime("%Y%m%d_%H%M%S")
        base_filename = f"{transcription.episode_guid}_{timestamp}"

        # Save JSON format with all metadata
        json_data = {
            "episode_guid": transcription.episode_guid,
            "generated_at": transcription.generated_at.isoformat(),
            "total_duration_seconds": transcription.total_duration_seconds,
            "total_processing_time_seconds": transcription.total_processing_time_seconds,
            "word_count": transcription.word_count,
            "chunk_count": transcription.chunk_count,
            "transcript_text": transcription.transcript_text,
            "provider": self.provider_name,
            "chunks": [
                {
                    "chunk_number": chunk.chunk_number,
                    "start_time_seconds": chunk.start_time_seconds,
                    "end_time_seconds": chunk.end_time_seconds,
                    "text": chunk.text,
                    "confidence": chunk.confidence,
                    "processing_time_seconds": chunk.processing_time_seconds
                }
                for chunk in transcription.chunks
            ]
        }

        json_path = output_path / f"{base_filename}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        # Save TXT format with headers
        txt_path = output_path / f"{base_filename}.txt"
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"Episode GUID: {transcription.episode_guid}\n")
            f.write(f"Generated: {transcription.generated_at.isoformat()}\n")
            f.write(f"Provider: {self.provider_name}\n")
            f.write(f"Duration: {transcription.total_duration_seconds:.1f} seconds\n")
            f.write(f"Word Count: {transcription.word_count}\n")
            f.write(f"Chunks: {transcription.chunk_count}\n")
            f.write(f"Processing Time: {transcription.total_processing_time_seconds:.1f} seconds\n")
            speed_ratio = transcription.total_duration_seconds / transcription.total_processing_time_seconds if transcription.total_processing_time_seconds > 0 else 0
            f.write(f"Speed: {speed_ratio:.1f}x realtime\n")
            f.write("-" * 50 + "\n\n")
            f.write(transcription.transcript_text)

        logger.info(f"Transcription saved: {json_path} and {txt_path}")
        return str(json_path), str(txt_path)


class OpenAIWhisperProvider(STTProvider):
    """
    OpenAI Whisper API provider for speech-to-text transcription
    """

    def __init__(self,
                 chunk_duration_minutes: int = 3,
                 model: str = "whisper-1",
                 max_cost_per_hour: float = 10.0,
                 max_retries: int = 3,
                 web_config: Optional['WebConfigManager'] = None):
        """
        Initialize OpenAI Whisper provider

        Args:
            chunk_duration_minutes: Duration of audio chunks
            model: OpenAI Whisper model to use
            max_cost_per_hour: Maximum cost per hour of audio (USD)
            max_retries: Maximum retry attempts for failed requests
            web_config: Web configuration manager for settings
        """
        super().__init__(chunk_duration_minutes)

        self.web_config = web_config or self._safe_create_web_config()

        # Load AI configuration for STT transcription
        if self.web_config:
            self.model = self.web_config.get_setting("ai_stt_transcription", "model", model)
            self.max_file_size_mb = self.web_config.get_setting("ai_stt_transcription", "max_file_size_mb", 20)

            # Validate file size limits against model capabilities
            self.max_file_size_mb = self._validate_and_adjust_file_size_limit(self.model, self.max_file_size_mb)
        else:
            self.model = model
            self.max_file_size_mb = 20

        self.max_cost_per_hour = max_cost_per_hour
        self.max_retries = max_retries

        # Cost tracking (Whisper is $0.006 per minute as of 2024)
        self.cost_per_minute = 0.006
        self.session_cost = 0.0
        self.session_start_time = time.time()

        # OpenAI client (initialized on first use)
        self._client = None
        self._initialized = False

        logger.info(f"OpenAI Whisper provider initialized: model={self.model}, max_cost=${max_cost_per_hour}/hour, max_file_size={self.max_file_size_mb}MB")

    def _safe_create_web_config(self) -> Optional['WebConfigManager']:
        """Safely create web config, return None if not available"""
        if WebConfigManager is None:
            return None
        try:
            return WebConfigManager()
        except Exception:
            return None

    def _validate_and_adjust_file_size_limit(self, model: str, requested_size_mb: int) -> int:
        """Validate and adjust file size limit based on model capabilities"""
        if not self.web_config:
            return requested_size_mb

        # Get model's maximum file size limit
        max_limit = self.web_config.get_model_limit('whisper', model, 'max_file_size_mb')
        if max_limit > 0 and requested_size_mb > max_limit:
            logger.warning(f"Requested {requested_size_mb}MB exceeds {model} limit of {max_limit}MB, adjusting to {max_limit}MB")
            return max_limit

        return requested_size_mb

    def initialize(self) -> bool:
        """Initialize OpenAI client"""
        if self._initialized:
            return True

        try:
            # Import OpenAI
            import openai

            # Get API key
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise PodcastError("OPENAI_API_KEY environment variable not set")

            # Initialize client
            self._client = openai.OpenAI(api_key=api_key)

            # Test connection with a simple API call
            try:
                models = self._client.models.list()
                available_models = [model.id for model in models.data]
                if self.model not in available_models:
                    logger.warning(f"Model {self.model} not found in available models. Using whisper-1 as fallback.")
                    self.model = "whisper-1"
            except Exception as e:
                logger.warning(f"Could not verify model availability: {e}")

            self._initialized = True
            logger.info("OpenAI Whisper provider initialized successfully")
            return True

        except ImportError as e:
            error_msg = f"OpenAI library not installed: {e}"
            logger.error(error_msg)
            raise PodcastError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to initialize OpenAI Whisper provider: {e}"
            logger.error(error_msg)
            raise PodcastError(error_msg) from e

    def transcribe_episode(self, audio_chunks: List[str], episode_guid: str) -> EpisodeTranscription:
        """
        Transcribe a complete episode using OpenAI Whisper API
        """
        if not audio_chunks:
            raise PodcastError("No audio chunks provided for transcription")

        # Initialize if needed
        if not self.initialize():
            raise PodcastError("Failed to initialize OpenAI Whisper provider")

        logger.info(f"Transcribing episode {episode_guid} with {len(audio_chunks)} chunks using OpenAI Whisper")
        start_time = datetime.now()

        # Check cost limits
        estimated_minutes = len(audio_chunks) * (self.chunk_duration_seconds / 60)
        estimated_cost = estimated_minutes * self.cost_per_minute

        session_duration_hours = (time.time() - self.session_start_time) / 3600
        if session_duration_hours > 0:
            hourly_rate = self.session_cost / session_duration_hours + (estimated_cost / session_duration_hours if session_duration_hours < 1 else estimated_cost)
            if hourly_rate > self.max_cost_per_hour:
                raise PodcastError(f"Cost limit exceeded: estimated ${hourly_rate:.2f}/hour > ${self.max_cost_per_hour}/hour limit")

        try:
            transcription_chunks = []
            total_processing_time = 0.0

            for i, chunk_path in enumerate(audio_chunks):
                chunk_start_time = i * self.chunk_duration_seconds
                chunk_result = self._transcribe_chunk(
                    chunk_path,
                    chunk_number=i+1,
                    start_time=chunk_start_time
                )
                transcription_chunks.append(chunk_result)
                total_processing_time += chunk_result.processing_time_seconds

                # Update cost tracking
                chunk_minutes = self.chunk_duration_seconds / 60
                chunk_cost = chunk_minutes * self.cost_per_minute
                self.session_cost += chunk_cost

                logger.debug(f"Transcribed chunk {i+1}/{len(audio_chunks)}: {len(chunk_result.text)} chars, ${chunk_cost:.4f}")

            # Combine all chunks into full transcript
            full_text = self._combine_chunks(transcription_chunks)
            word_count = len(full_text.split())

            # Calculate total duration
            total_duration = len(audio_chunks) * self.chunk_duration_seconds
            if transcription_chunks:
                # Use actual end time of last chunk if available
                total_duration = transcription_chunks[-1].end_time_seconds

            episode_transcription = EpisodeTranscription(
                episode_guid=episode_guid,
                chunks=transcription_chunks,
                total_duration_seconds=total_duration,
                total_processing_time_seconds=total_processing_time,
                word_count=word_count,
                chunk_count=len(transcription_chunks),
                transcript_text=full_text,
                generated_at=start_time
            )

            processing_duration = (datetime.now() - start_time).total_seconds()

            logger.info(f"Episode transcription complete: {word_count} words, "
                       f"{len(transcription_chunks)} chunks, "
                       f"${self.session_cost:.4f} total cost")

            return episode_transcription

        except Exception as e:
            error_msg = f"Failed to transcribe episode {episode_guid}: {e}"
            logger.error(error_msg)
            raise PodcastError(error_msg) from e

    @retry_with_backoff(max_retries=3, backoff_factor=2.0)
    def _transcribe_chunk(self, chunk_path: str, chunk_number: int, start_time: float) -> TranscriptionChunk:
        """Transcribe a single audio chunk using OpenAI Whisper"""
        chunk_start = datetime.now()

        try:
            logger.debug(f"Transcribing chunk {chunk_number}: {chunk_path}")

            # Validate file size
            chunk_file = Path(chunk_path)
            if not chunk_file.exists():
                raise PodcastError(f"Chunk file not found: {chunk_path}")

            file_size_bytes = chunk_file.stat().st_size
            file_size_mb = file_size_bytes / (1024 * 1024)

            if file_size_mb > self.max_file_size_mb:
                raise PodcastError(f"Chunk file {chunk_path} ({file_size_mb:.1f}MB) exceeds maximum size limit of {self.max_file_size_mb}MB")

            logger.debug(f"Chunk file size: {file_size_mb:.2f}MB (within {self.max_file_size_mb}MB limit)")

            # Open audio file
            with open(chunk_path, 'rb') as audio_file:
                # Call OpenAI Whisper API
                response = self._client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    response_format='verbose_json',  # Get detailed response with timestamps
                    language='en',  # Specify English for better performance
                    temperature=0  # More deterministic output
                )

            # Extract text and metadata
            text = response.text.strip() if hasattr(response, 'text') else ""

            # Extract duration if available (from segments)
            chunk_duration = self.chunk_duration_seconds
            if hasattr(response, 'segments') and response.segments:
                last_segment = response.segments[-1]
                if hasattr(last_segment, 'end'):
                    chunk_duration = min(last_segment.end, self.chunk_duration_seconds)

            # Calculate confidence (OpenAI doesn't provide confidence scores, use 1.0)
            confidence = 1.0

            processing_time = (datetime.now() - chunk_start).total_seconds()

            return TranscriptionChunk(
                chunk_number=chunk_number,
                start_time_seconds=start_time,
                end_time_seconds=start_time + chunk_duration,
                text=text,
                confidence=confidence,
                processing_time_seconds=processing_time
            )

        except Exception as e:
            error_msg = f"Failed to transcribe chunk {chunk_number} ({chunk_path}): {e}"
            logger.error(error_msg)
            raise PodcastError(error_msg) from e

    def get_model_info(self) -> Dict:
        """Get information about the OpenAI Whisper provider"""
        info = {
            "provider": "openai_whisper",
            "model": self.model,
            "status": "initialized" if self._initialized else "not_initialized",
            "cost_per_minute": self.cost_per_minute,
            "max_cost_per_hour": self.max_cost_per_hour,
            "session_cost": self.session_cost,
            "max_file_size_mb": self.max_file_size_mb
        }

        if self._initialized and self._client:
            try:
                info["api_key_configured"] = bool(os.getenv('OPENAI_API_KEY'))
            except:
                info["api_key_configured"] = False

        return info


def create_stt_provider(provider_name: str = "openai", **kwargs) -> STTProvider:
    """
    Factory function to create STT provider based on provider name

    Args:
        provider_name: Name of the STT provider ("openai")
        **kwargs: Provider-specific arguments

    Returns:
        STT provider instance

    Raises:
        PodcastError: If provider not supported
    """
    provider_name = provider_name.lower()

    if provider_name == "openai" or provider_name == "openai_whisper":
        return OpenAIWhisperProvider(**kwargs)
    else:
        raise PodcastError(f"Unsupported STT provider: {provider_name}")


def get_stt_provider_from_env() -> STTProvider:
    """
    Create STT provider based on STT_PROVIDER environment variable

    Returns:
        STT provider instance

    Raises:
        PodcastError: If STT_PROVIDER not set or unsupported
    """
    provider_name = os.getenv('STT_PROVIDER')
    if not provider_name:
        raise PodcastError("STT_PROVIDER environment variable not set")

    # Get additional configuration from environment
    kwargs = {}

    # OpenAI Whisper specific configuration
    if provider_name.lower() in ["openai", "openai_whisper"]:
        if os.getenv('WHISPER_MODEL'):
            kwargs['model'] = os.getenv('WHISPER_MODEL')
        if os.getenv('WHISPER_MAX_COST_PER_HOUR'):
            kwargs['max_cost_per_hour'] = float(os.getenv('WHISPER_MAX_COST_PER_HOUR'))

    return create_stt_provider(provider_name, **kwargs)