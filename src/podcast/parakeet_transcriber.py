#!/usr/bin/env python3
"""
Nvidia Parakeet ASR Transcription Pipeline
Handles transcribing audio chunks using Nvidia's Parakeet model via Hugging Face.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
import tempfile

from ..utils.error_handling import retry_with_backoff, PodcastError
from ..utils.logging_config import get_logger

logger = get_logger(__name__)

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

class ParakeetTranscriber:
    """
    Nvidia Parakeet ASR transcriber using Hugging Face Transformers
    """
    
    def __init__(self, 
                 model_name: str = "nvidia/parakeet-rnnt-0.6b",
                 device: str = "auto",
                 chunk_duration_minutes: int = 10):
        """
        Initialize Parakeet transcriber
        
        Args:
            model_name: Hugging Face model identifier
            device: Device to use ('cpu', 'cuda', 'auto')
            chunk_duration_minutes: Duration of audio chunks
        """
        self.model_name = model_name
        self.device = device
        self.chunk_duration_seconds = chunk_duration_minutes * 60
        
        # Will be initialized on first use
        self._model = None
        self._processor = None
        self._initialized = False
        
        logger.info(f"ParakeetTranscriber initialized with model: {model_name}")
    
    def _initialize_model(self):
        """Initialize the model and processor (lazy loading)"""
        if self._initialized:
            return
        
        logger.info(f"Loading Parakeet model: {self.model_name}")
        
        try:
            # Import libraries
            import torch
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
            
            # Determine device
            if self.device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                device = self.device
            
            logger.info(f"Using device: {device}")
            
            # Load model and processor
            self._processor = AutoProcessor.from_pretrained(self.model_name)
            self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                low_cpu_mem_usage=True,
                use_safetensors=True
            )
            self._model.to(device)
            
            # Create pipeline
            self._pipeline = pipeline(
                "automatic-speech-recognition",
                model=self._model,
                tokenizer=self._processor.tokenizer,
                feature_extractor=self._processor.feature_extractor,
                device=device,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                return_timestamps=True
            )
            
            self._device = device
            self._initialized = True
            logger.info("Parakeet model loaded successfully")
            
        except ImportError as e:
            error_msg = f"Required libraries not installed: {e}"
            logger.error(error_msg)
            raise PodcastError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to initialize Parakeet model: {e}"
            logger.error(error_msg)
            raise PodcastError(error_msg) from e
    
    @retry_with_backoff(max_retries=2, backoff_factor=1.5)
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
        if not audio_chunks:
            raise PodcastError("No audio chunks provided for transcription")
        
        # Initialize model if needed
        self._initialize_model()
        
        logger.info(f"Transcribing episode {episode_guid} with {len(audio_chunks)} chunks")
        start_time = datetime.now()
        
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
                
                logger.debug(f"Transcribed chunk {i+1}/{len(audio_chunks)}: {len(chunk_result.text)} chars")
            
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
            speed_ratio = total_duration / processing_duration if processing_duration > 0 else 0
            
            logger.info(f"Episode transcription complete: {word_count} words, "
                       f"{len(transcription_chunks)} chunks, "
                       f"{speed_ratio:.1f}x realtime speed")
            
            return episode_transcription
            
        except Exception as e:
            error_msg = f"Failed to transcribe episode {episode_guid}: {e}"
            logger.error(error_msg)
            raise PodcastError(error_msg) from e
    
    def _transcribe_chunk(self, chunk_path: str, chunk_number: int, 
                         start_time: float) -> TranscriptionChunk:
        """Transcribe a single audio chunk"""
        chunk_start = datetime.now()
        
        try:
            logger.debug(f"Transcribing chunk {chunk_number}: {chunk_path}")
            
            # Transcribe using pipeline
            result = self._pipeline(
                chunk_path,
                return_timestamps=True,
                generate_kwargs={"language": "english", "task": "transcribe"}
            )
            
            # Extract text and timestamps
            if isinstance(result, dict):
                text = result.get('text', '').strip()
                chunks = result.get('chunks', [])
                
                # Calculate confidence (if available)
                confidence = 1.0  # Parakeet doesn't typically return confidence scores
                
                # If we have timestamp chunks, use them to determine actual end time
                if chunks and len(chunks) > 0:
                    last_chunk = chunks[-1]
                    chunk_duration = last_chunk.get('timestamp', [0, self.chunk_duration_seconds])[1]
                else:
                    chunk_duration = self.chunk_duration_seconds
                
            else:
                text = str(result).strip()
                confidence = 1.0
                chunk_duration = self.chunk_duration_seconds
            
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
            f.write(f"Duration: {transcription.total_duration_seconds:.1f} seconds\n")
            f.write(f"Word Count: {transcription.word_count}\n")
            f.write(f"Chunks: {transcription.chunk_count}\n")
            f.write(f"Processing Time: {transcription.total_processing_time_seconds:.1f} seconds\n")
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
        """Get information about the loaded model"""
        if not self._initialized:
            return {"status": "not_initialized", "model_name": self.model_name}
        
        try:
            import torch
            
            return {
                "status": "initialized",
                "model_name": self.model_name,
                "device": self._device,
                "pytorch_version": torch.__version__,
                "cuda_available": torch.cuda.is_available(),
                "gpu_memory": torch.cuda.get_device_properties(0).total_memory if torch.cuda.is_available() else None
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


def create_parakeet_transcriber(model_name: str = "nvidia/parakeet-rnnt-0.6b",
                               device: str = "auto",
                               chunk_duration_minutes: int = 10) -> ParakeetTranscriber:
    """Factory function to create Parakeet transcriber"""
    return ParakeetTranscriber(model_name, device, chunk_duration_minutes)


# CLI testing function
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python parakeet_transcriber.py <episode_guid> <chunk1.mp3> [chunk2.mp3] ...")
        sys.exit(1)
    
    episode_guid = sys.argv[1]
    audio_chunks = sys.argv[2:]
    
    # Verify all chunk files exist
    for chunk in audio_chunks:
        if not os.path.exists(chunk):
            print(f"Error: Audio chunk not found: {chunk}")
            sys.exit(1)
    
    transcriber = create_parakeet_transcriber()
    
    try:
        print("Loading Parakeet model...")
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