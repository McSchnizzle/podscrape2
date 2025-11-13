#!/usr/bin/env python3
"""
OpenAI Whisper Local Transcription Pipeline
Handles transcribing audio chunks using the local OpenAI Whisper model.
Direct replacement for Parakeet MLX transcriber - no API key required.
"""

import os
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
import tempfile

logger = logging.getLogger(__name__)

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

class PodcastError(Exception):
    """Custom exception for podcast processing errors"""
    pass

def retry_with_backoff(max_retries=2, backoff_factor=1.5):
    """Simple retry decorator - does NOT retry PodcastError (permanent failures)"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except PodcastError:
                    # Don't retry PodcastError - these are permanent failures
                    # (corrupt audio, missing files, validation failures)
                    raise
                except Exception as e:
                    if attempt == max_retries:
                        raise
                    time.sleep(backoff_factor ** attempt)
            return None
        return wrapper
    return decorator

class OpenAIWhisperTranscriber:
    """
    Local OpenAI Whisper transcriber - direct replacement for Parakeet MLX
    Uses the open-source Whisper model locally (no API key required)
    """

    def __init__(self,
                 model: str = None,
                 chunk_duration_minutes: int = 3,
                 device: str = "auto"):
        """
        Initialize OpenAI Whisper transcriber

        Args:
            model: Whisper model size ("tiny", "base", "small", "medium", "large")
                   If None, reads from WHISPER_MODEL environment variable (default: "base")
            chunk_duration_minutes: Duration of audio chunks
            device: Device to use ("cpu", "cuda", "auto")
        """
        # Use environment variable if model not specified
        if model is None:
            model = os.getenv("WHISPER_MODEL", "base")

        self.model = model
        self.chunk_duration_seconds = chunk_duration_minutes * 60
        self.device = device

        # Model will be loaded on first use
        self._whisper_model = None
        self._initialized = False

        logger.info(f"OpenAI Whisper local transcriber initialized: model={model}, device={device}")

    def _initialize_model(self):
        """Initialize local Whisper model with corrupted cache recovery"""
        if self._initialized:
            return

        logger.info(f"Loading local OpenAI Whisper model: {self.model}")

        try:
            import whisper
            import torch

            # Determine device
            if self.device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                device = self.device

            logger.info(f"Using device: {device}")

            # Load Whisper model
            self._whisper_model = whisper.load_model(self.model, device=device)
            self._device = device

            self._initialized = True
            logger.info(f"OpenAI Whisper model '{self.model}' loaded successfully on {device}")

        except ImportError as e:
            error_msg = f"OpenAI Whisper library not installed: pip install openai-whisper"
            logger.error(error_msg)
            raise PodcastError(error_msg) from e
        except RuntimeError as e:
            # CRITICAL FIX: Handle SHA256 checksum errors (corrupted model cache)
            # These are transient errors that should be retried after cleaning cache
            error_str = str(e)
            if 'SHA256 checksum does not' in error_str or 'checksum' in error_str.lower():
                logger.warning(f"Detected corrupted Whisper model cache: {error_str}")

                # Try to clean up corrupted model file
                try:
                    import os
                    cache_dir = Path.home() / ".cache" / "whisper"
                    model_file = cache_dir / f"{self.model}.pt"

                    if model_file.exists():
                        logger.info(f"Deleting corrupted model cache: {model_file}")
                        model_file.unlink()
                        logger.info("Corrupted cache deleted - will retry download on next attempt")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up corrupted cache: {cleanup_error}")

                # Raise regular Exception (not PodcastError) to allow retry
                error_msg = f"Whisper model cache corrupted (SHA256 mismatch) - cache cleaned, retry needed: {e}"
                logger.error(error_msg)
                raise Exception(error_msg) from e
            else:
                # Other RuntimeError - treat as permanent failure
                error_msg = f"Failed to load Whisper model: {e}"
                logger.error(error_msg)
                raise PodcastError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to load Whisper model: {e}"
            logger.error(error_msg)
            raise PodcastError(error_msg) from e

    @retry_with_backoff(max_retries=2, backoff_factor=1.5)
    def transcribe_episode(self, audio_chunks: List[str], episode_guid: str,
                          in_progress_file: Optional[str] = None,
                          episode_repo=None) -> EpisodeTranscription:
        """
        Transcribe a complete episode from audio chunks

        Args:
            audio_chunks: List of paths to audio chunk files
            episode_guid: Unique episode identifier
            in_progress_file: Path to write in-progress transcript (optional, ignored for now)
            episode_repo: EpisodeRepository for incremental database writes (memory-efficient mode)

        Returns:
            EpisodeTranscription object with complete transcription

        Raises:
            PodcastError: If transcription fails
        """
        if not audio_chunks:
            raise PodcastError("No audio chunks provided for transcription")

        # Initialize client if needed
        self._initialize_model()

        memory_efficient = episode_repo is not None
        if memory_efficient:
            logger.info(f"Transcribing episode {episode_guid} with {len(audio_chunks)} chunks using OpenAI Whisper (MEMORY-EFFICIENT MODE)")
        else:
            logger.info(f"Transcribing episode {episode_guid} with {len(audio_chunks)} chunks using OpenAI Whisper")

        start_time = datetime.now()

        # No cost limits needed for local Whisper - it's free!

        try:
            transcription_chunks = []
            total_processing_time = 0.0
            current_word_count = 0

            # Initialize in-progress file if provided
            if in_progress_file:
                with open(in_progress_file, 'w', encoding='utf-8') as f:
                    f.write(f"Transcription in progress for episode {episode_guid}\n")
                    f.write(f"Processing {len(audio_chunks)} chunks...\n\n")

            for i, chunk_path in enumerate(audio_chunks):
                logger.info(f"Processing chunk {i+1}/{len(audio_chunks)}: {chunk_path}")

                chunk_start_time = i * self.chunk_duration_seconds
                chunk_result = self._transcribe_chunk(
                    chunk_path,
                    chunk_number=i+1,
                    start_time=chunk_start_time
                )
                transcription_chunks.append(chunk_result)
                total_processing_time += chunk_result.processing_time_seconds

                logger.info(f"Completed chunk {i+1}/{len(audio_chunks)}: {len(chunk_result.text)} chars, "
                           f"{chunk_result.processing_time_seconds:.1f}s processing time")

                # MEMORY OPTIMIZATION: Write chunk to database immediately instead of accumulating in memory
                if memory_efficient and chunk_result.text.strip():
                    current_word_count = episode_repo.append_transcript_chunk(
                        episode_guid,
                        chunk_result.text.strip(),
                        i+1
                    )
                    logger.debug(f"Chunk {i+1} written to database (total words: {current_word_count:,})")

                # Update in-progress file with completed chunks
                if in_progress_file and chunk_result.text.strip():
                    with open(in_progress_file, 'a', encoding='utf-8') as f:
                        f.write(f"[Chunk {i+1}] {chunk_result.text.strip()}\n\n")

            # Calculate word count based on mode
            if memory_efficient:
                # Memory-efficient mode: word count from database
                word_count = current_word_count
                full_text = ""  # Not needed in memory-efficient mode
            else:
                # Traditional mode: combine chunks in memory
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
                transcript_text=full_text,  # Empty in memory-efficient mode
                generated_at=start_time
            )

            processing_duration = (datetime.now() - start_time).total_seconds()
            speed_ratio = total_duration / processing_duration if processing_duration > 0 else 0

            logger.info(f"Episode transcription complete: {word_count} words, "
                       f"{len(transcription_chunks)} chunks, "
                       f"{speed_ratio:.1f}x realtime speed")

            # Finalize transcript in database if using memory-efficient mode
            if memory_efficient:
                episode_repo.finalize_transcript(episode_guid)
                logger.info(f"Transcript finalized in database (memory-efficient mode)")

            # Write final complete transcript to in-progress file (traditional mode only)
            if in_progress_file and not memory_efficient:
                with open(in_progress_file, 'w', encoding='utf-8') as f:
                    f.write(full_text)
                logger.info(f"Complete transcript written to in-progress file: {in_progress_file}")

            return episode_transcription

        except Exception as e:
            error_msg = f"Failed to transcribe episode {episode_guid}: {e}"
            logger.error(error_msg)
            raise PodcastError(error_msg) from e

    def _transcribe_chunk(self, chunk_path: str, chunk_number: int, start_time: float) -> TranscriptionChunk:
        """Transcribe a single audio chunk using OpenAI Whisper"""
        chunk_start = datetime.now()

        try:
            logger.debug(f"Transcribing chunk {chunk_number}: {chunk_path}")

            # Validate chunk file exists and has content
            import os
            if not os.path.exists(chunk_path):
                raise PodcastError(f"Chunk file not found: {chunk_path}")

            chunk_size = os.path.getsize(chunk_path)
            if chunk_size < 10240:  # 10KB minimum
                raise PodcastError(f"Chunk file too small ({chunk_size} bytes): {chunk_path}")

            # Use local Whisper model to transcribe with enhanced error handling
            result = self._whisper_model.transcribe(
                chunk_path,
                language='en',  # Specify English for better performance
                temperature=0,  # More deterministic output
                verbose=False,  # Reduce logging noise
                fp16=False      # Use FP32 instead of FP16 to avoid warnings
            )

            # Extract text
            text = result.get('text', '').strip()

            # Extract duration if available (from segments)
            chunk_duration = self.chunk_duration_seconds
            if 'segments' in result and result['segments']:
                last_segment = result['segments'][-1]
                if 'end' in last_segment:
                    chunk_duration = min(last_segment['end'], self.chunk_duration_seconds)

            # Whisper doesn't provide confidence scores, use 1.0
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

        except RuntimeError as e:
            # Catch Whisper tensor errors specifically
            error_str = str(e)
            if 'cannot reshape tensor' in error_str or 'shape' in error_str.lower():
                error_msg = (
                    f"Whisper tensor error for chunk {chunk_number} - "
                    f"likely corrupt or invalid audio data: {chunk_path}"
                )
                logger.error(error_msg)
                raise PodcastError(error_msg) from e
            else:
                error_msg = f"Whisper runtime error for chunk {chunk_number}: {e}"
                logger.error(error_msg)
                raise PodcastError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to transcribe chunk {chunk_number} ({chunk_path}): {e}"
            logger.error(error_msg)
            raise PodcastError(error_msg) from e

    def _combine_chunks(self, chunks: List[TranscriptionChunk]) -> str:
        """Combine transcription chunks into complete text"""
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
            "model": f"openai-{self.model}",
            "provider": "openai-whisper",
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
            f.write(f"Provider: OpenAI Whisper ({self.model})\n")
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

    def load_transcription(self, json_path: str) -> EpisodeTranscription:
        """Load transcription from JSON file"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            chunks = [
                TranscriptionChunk(
                    chunk_number=chunk_data["chunk_number"],
                    start_time_seconds=chunk_data["start_time_seconds"],
                    end_time_seconds=chunk_data["end_time_seconds"],
                    text=chunk_data["text"],
                    confidence=chunk_data["confidence"],
                    processing_time_seconds=chunk_data["processing_time_seconds"]
                )
                for chunk_data in data["chunks"]
            ]

            return EpisodeTranscription(
                episode_guid=data["episode_guid"],
                chunks=chunks,
                total_duration_seconds=data["total_duration_seconds"],
                total_processing_time_seconds=data["total_processing_time_seconds"],
                word_count=data["word_count"],
                chunk_count=data["chunk_count"],
                transcript_text=data["transcript_text"],
                generated_at=datetime.fromisoformat(data["generated_at"])
            )

        except Exception as e:
            error_msg = f"Failed to load transcription from {json_path}: {e}"
            logger.error(error_msg)
            raise PodcastError(error_msg) from e

    def get_model_info(self) -> Dict:
        """Get information about the local OpenAI Whisper model"""
        info = {
            "status": "initialized" if self._initialized else "not_initialized",
            "provider": "openai-whisper-local",
            "model": self.model,
            "device": getattr(self, '_device', self.device),
            "framework": "PyTorch + OpenAI Whisper"
        }

        if self._initialized:
            info["model_loaded"] = True

        return info


def create_openai_whisper_transcriber(model: str = None,
                                     chunk_duration_minutes: int = 3,
                                     device: str = "auto") -> OpenAIWhisperTranscriber:
    """
    Factory function to create local OpenAI Whisper transcriber

    Args:
        model: Whisper model size ("tiny", "base", "small", "medium", "large")
               If None, reads from WHISPER_MODEL environment variable (default: "base")
        chunk_duration_minutes: Audio chunk duration
        device: Computing device ("cpu", "cuda", "auto")
    """
    return OpenAIWhisperTranscriber(model, chunk_duration_minutes, device)


# CLI testing function
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python openai_whisper_transcriber.py <episode_guid> <chunk1.mp3> [chunk2.mp3] ...")
        sys.exit(1)

    episode_guid = sys.argv[1]
    audio_chunks = sys.argv[2:]

    # Verify all chunk files exist
    for chunk in audio_chunks:
        if not os.path.exists(chunk):
            print(f"Error: Audio chunk not found: {chunk}")
            sys.exit(1)

    transcriber = create_openai_whisper_transcriber()

    try:
        print("Initializing OpenAI Whisper...")
        model_info = transcriber.get_model_info()
        print(f"Model: {model_info}")

        print(f"Transcribing {len(audio_chunks)} chunks...")
        transcription = transcriber.transcribe_episode(audio_chunks, episode_guid)

        print(f"Transcription complete!")
        print(f"Word count: {transcription.word_count}")
        print(f"Duration: {transcription.total_duration_seconds:.1f}s")
        print(f"Processing time: {transcription.total_processing_time_seconds:.1f}s")
        print(f"Speed: {transcription.total_duration_seconds/transcription.total_processing_time_seconds:.1f}x realtime")

        # Save to temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path, txt_path = transcriber.save_transcription(transcription, temp_dir)
            print(f"Saved to: {json_path}")

            # Show first 200 characters
            print(f"Transcript preview: {transcription.transcript_text[:200]}...")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)