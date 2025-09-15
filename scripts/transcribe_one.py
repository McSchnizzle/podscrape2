#!/usr/bin/env python3
"""
CLI tool for transcribing single audio files using the new STT provider system.
Useful for testing and validation of different STT providers.
"""

import os
import sys
import tempfile
import argparse
import logging
from pathlib import Path
from typing import List

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pipeline.stt.providers import get_stt_provider_from_env, create_stt_provider, PodcastError
from src.podcast.audio_processor import create_audio_processor

def main():
    parser = argparse.ArgumentParser(description='Transcribe single audio file using STT provider')
    parser.add_argument('audio_file', help='Path to audio file to transcribe')
    parser.add_argument('--provider', default=None,
                       help='STT provider to use (default: from STT_PROVIDER env var)')
    parser.add_argument('--episode-id', default='test-episode',
                       help='Episode ID for output files (default: test-episode)')
    parser.add_argument('--output-dir', default='./transcribe_output',
                       help='Output directory for transcriptions (default: ./transcribe_output)')
    parser.add_argument('--chunk-duration', type=int, default=3,
                       help='Chunk duration in minutes (default: 3)')
    parser.add_argument('--model', default=None,
                       help='Model to use (provider-specific, e.g., whisper-1 for OpenAI)')
    parser.add_argument('--max-cost', type=float, default=5.0,
                       help='Maximum cost per hour for OpenAI (default: $5.00)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--keep-chunks', action='store_true',
                       help='Keep audio chunks after transcription')

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Validate audio file
    audio_file_path = Path(args.audio_file)
    if not audio_file_path.exists():
        print(f"Error: Audio file not found: {args.audio_file}")
        sys.exit(1)

    print(f"Transcribing: {args.audio_file}")
    print(f"Episode ID: {args.episode_id}")
    print(f"Output directory: {args.output_dir}")

    try:
        # Create STT provider
        if args.provider:
            provider_kwargs = {'chunk_duration_minutes': args.chunk_duration}
            if args.provider.lower() == 'openai':
                if args.model:
                    provider_kwargs['model'] = args.model
                provider_kwargs['max_cost_per_hour'] = args.max_cost

            stt_provider = create_stt_provider(args.provider, **provider_kwargs)
        else:
            # Use environment variable
            stt_provider = get_stt_provider_from_env()

        print(f"Using STT provider: {stt_provider.__class__.__name__}")

        # Get provider info
        provider_info = stt_provider.get_model_info()
        print(f"Provider info: {provider_info}")

        # Create audio processor for chunking
        with tempfile.TemporaryDirectory() as temp_dir:
            chunk_dir = Path(temp_dir) / "chunks"
            audio_processor = create_audio_processor(
                audio_cache_dir=temp_dir,
                chunk_dir=str(chunk_dir),
                chunk_duration_minutes=args.chunk_duration
            )

            # If file is already small enough, just copy it
            audio_info = audio_processor.get_audio_info(str(audio_file_path))
            duration_seconds = audio_info.get('duration', 0)
            chunk_duration_seconds = args.chunk_duration * 60

            print(f"Audio duration: {duration_seconds:.1f}s")

            if duration_seconds <= chunk_duration_seconds:
                # Single chunk - just copy the file
                episode_id_clean = args.episode_id.replace('-', '')[:6]
                chunk_dir.mkdir(parents=True, exist_ok=True)
                single_chunk_dir = chunk_dir / episode_id_clean
                single_chunk_dir.mkdir(exist_ok=True)

                chunk_path = single_chunk_dir / f"{episode_id_clean}_chunk_001.mp3"
                import shutil
                shutil.copy2(str(audio_file_path), str(chunk_path))
                audio_chunks = [str(chunk_path)]
                print(f"Audio fits in single chunk: {chunk_path}")
            else:
                # Need to chunk the audio
                print(f"Chunking audio into {args.chunk_duration}-minute segments...")
                audio_chunks = audio_processor.chunk_audio(str(audio_file_path), args.episode_id)
                print(f"Created {len(audio_chunks)} chunks")

            # Transcribe the episode
            print("Starting transcription...")
            transcription = stt_provider.transcribe_episode(audio_chunks, args.episode_id)

            # Save transcription
            output_dir = Path(args.output_dir)
            json_path, txt_path = stt_provider.save_transcription(transcription, str(output_dir))

            # Print results
            print("\n" + "="*50)
            print("TRANSCRIPTION COMPLETE")
            print("="*50)
            print(f"Word count: {transcription.word_count}")
            print(f"Duration: {transcription.total_duration_seconds:.1f}s")
            print(f"Processing time: {transcription.total_processing_time_seconds:.1f}s")
            print(f"Chunks: {transcription.chunk_count}")

            if hasattr(stt_provider, 'session_cost'):
                print(f"Cost: ${stt_provider.session_cost:.4f}")

            processing_speed = transcription.total_duration_seconds / transcription.total_processing_time_seconds if transcription.total_processing_time_seconds > 0 else 0
            print(f"Speed: {processing_speed:.1f}x realtime")

            print(f"\nSaved to:")
            print(f"  JSON: {json_path}")
            print(f"  TXT: {txt_path}")

            # Show transcript preview
            preview_length = 300
            if len(transcription.transcript_text) > preview_length:
                preview = transcription.transcript_text[:preview_length] + "..."
            else:
                preview = transcription.transcript_text

            print(f"\nTranscript preview:")
            print("-" * 30)
            print(preview)

            # Keep chunks if requested
            if args.keep_chunks:
                chunk_output_dir = output_dir / "chunks"
                chunk_output_dir.mkdir(exist_ok=True)
                for i, chunk_path in enumerate(audio_chunks):
                    chunk_file = Path(chunk_path)
                    if chunk_file.exists():
                        output_chunk_path = chunk_output_dir / f"chunk_{i+1:03d}.mp3"
                        import shutil
                        shutil.copy2(str(chunk_file), str(output_chunk_path))
                print(f"\nChunks saved to: {chunk_output_dir}")

    except PodcastError as e:
        print(f"Transcription error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()