#!/usr/bin/env python3
"""
TTS Audio Generation Phase Script - Text-to-Speech Generation
Independent script for Phase 5: Generate TTS audio for digest scripts
Reads JSON input from digest phase or direct digest data.
"""

import os
import sys
import json
import logging
from datetime import datetime, date
from pathlib import Path
import argparse
from dataclasses import asdict, is_dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Bootstrap phase initialization
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))
from src.utils.phase_bootstrap import bootstrap_phase
bootstrap_phase()



def resolve_dry_run_flag(cli_flag: bool) -> bool:
    env_value = os.getenv("DRY_RUN")
    if env_value is not None:
        return env_value.strip().lower() in {"1", "true", "yes", "on"}
    return cli_flag
from src.database.models import get_digest_repo
from src.audio.complete_audio_processor import CompleteAudioProcessor

# Import centralized logging
try:
    from src.utils.logging_config import setup_phase_logging
except ImportError:
    from utils.logging_config import setup_phase_logging

def serialize_for_json(obj):
    """
    Recursively convert objects to JSON-serializable format.
    Handles dataclasses and datetime objects properly.
    """
    if obj is None:
        return None
    elif is_dataclass(obj):
        # Convert dataclass to dict and recursively process fields
        return serialize_for_json(asdict(obj))
    elif isinstance(obj, (datetime, date)):
        # Convert datetime/date to ISO string
        return obj.isoformat()
    elif isinstance(obj, dict):
        # Recursively process dictionary values
        return {key: serialize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        # Recursively process list/tuple items
        return [serialize_for_json(item) for item in obj]
    else:
        # Return primitive types as-is
        return obj

class TTSRunner:
    """TTS audio generation phase"""

    def __init__(self, dry_run: bool = False, limit: int = None, verbose: bool = False):
        # Set up phase-specific logging
        self.pipeline_logger = setup_phase_logging("tts", verbose=verbose, console_output=True)
        self.logger = self.pipeline_logger.get_logger()

        self.dry_run = dry_run
        self.limit = limit
        self.verbose = verbose

        # Initialize database configuration reader
        from src.config.web_config import WebConfigReader
        self.config_reader = WebConfigReader()

        # Get settings from database
        self.tts_config = self.config_reader.get_ai_tts_config()

        # Initialize repositories and components
        self.digest_repo = get_digest_repo()
        self.complete_audio_processor = CompleteAudioProcessor()

        # Verify API keys
        self._verify_dependencies()

        self.logger.info("TTS audio generation initialized")
        self.logger.info(f"Database settings - Model: {self.tts_config['model']}, "
                        f"Max characters: {self.tts_config['max_characters']}")

    def _verify_dependencies(self):
        """Verify required dependencies"""
        self.logger.info("Verifying dependencies...")

        # Check ElevenLabs API key
        elevenlabs_key = os.getenv('ELEVENLABS_API_KEY')
        if not elevenlabs_key or elevenlabs_key.startswith('test-') or elevenlabs_key == 'your-key-here':
            self.logger.warning("ElevenLabs API key not configured - TTS may not work")
        else:
            self.logger.info("✓ ElevenLabs API key configured")

    def generate_audio(self):
        """Generate TTS audio from database (database-first approach)"""

        self.pipeline_logger.log_phase_start("TTS Audio Generation Phase")

        # Get digests that need TTS processing (have script but no MP3)
        self.logger.info("🔍 Finding digests pending TTS processing...")
        all_pending_digests = self.digest_repo.get_digests_pending_tts()

        if not all_pending_digests:
            self.logger.info("📄 No digests found pending TTS processing")
            return {
                'success': True,
                'audio_generated': 0,
                'audio_results': [],
                'message': "No digests pending TTS processing"
            }

        # Process ALL pending digests (supports multiple digests per topic per day)
        digests = all_pending_digests
        self.logger.info(f"📄 Found {len(digests)} digests pending TTS processing")
        self.logger.info(f"✓ Processing all digests (supports multiple per topic per day)")

        # Apply limit
        if self.limit is not None:
            digests = digests[:self.limit]

        # Use parallel processing for better performance (40-70% time reduction)
        if len(digests) > 1 and not self.dry_run:
            self.logger.info(f"Generating audio for {len(digests)} digests in parallel (max 5 concurrent)")
            audio_results = self._generate_audio_parallel(digests)
        else:
            self.logger.info(f"Generating audio for {len(digests)} digests sequentially")
            audio_results = self._generate_audio_sequential(digests)

        # Summary
        successful = [r for r in audio_results if r.get('success') and not r.get('skipped')]
        skipped = [r for r in audio_results if r.get('skipped')]
        failed = [r for r in audio_results if not r.get('success')]

        self.logger.info(f"\n✅ AUDIO GENERATION COMPLETE:")
        self.logger.info(f"   🎵 Generated: {len(successful)} MP3 files")
        self.logger.info(f"   ⏭️  Skipped: {len(skipped)} (no qualifying episodes)")
        self.logger.info(f"   ❌ Failed: {len(failed)}")

        for result in successful:
            audio_metadata = result.get('audio_metadata')
            if audio_metadata:
                if isinstance(audio_metadata, dict):
                    file_path = audio_metadata.get('file_path', 'Unknown')
                else:
                    file_path = getattr(audio_metadata, 'file_path', 'Unknown')
                file_name = Path(file_path).name if file_path != 'Unknown' else 'Unknown'
                self.logger.info(f"      • {result['topic']}: {file_name}")

        # Log completion
        self.pipeline_logger.log_phase_complete(
            f"Generated {len(successful)} audio files" +
            (f" ({len(skipped)} skipped, {len(failed)} failed)" if (skipped or failed) else "")
        )

        return {
            'success': len(failed) == 0,
            'audio_generated': len(successful),
            'audio_skipped': len(skipped),
            'audio_failed': len(failed),
            'audio_results': audio_results
        }

    def _generate_audio_sequential(self, digests):
        """Generate audio sequentially (original behavior)"""
        audio_results = []

        for i, digest_data in enumerate(digests, 1):
            try:
                # Process single digest
                digest, result = self._process_single_digest(digest_data, i, len(digests))
                if result:
                    audio_results.append(result)
                    continue

                if self.dry_run:
                    self.logger.info("🔍 DRY RUN: Would generate audio")
                    audio_results.append({
                        'digest_id': digest.id,
                        'topic': digest.topic,
                        'success': True,
                        'skipped': False,
                        'status': 'dry_run',
                        'audio_metadata': None
                    })
                    continue

                # Generate audio
                result = self._generate_audio_for_digest(digest)
                audio_results.append(result)

            except Exception as e:
                self.logger.error(f"Failed to process digest: {e}")
                audio_results.append({
                    'success': False,
                    'error': str(e)
                })

        return audio_results

    def _generate_audio_parallel(self, digests):
        """Generate audio in parallel using ThreadPoolExecutor"""
        audio_results = []
        MAX_WORKERS = 5  # Conservative limit for ElevenLabs API

        # First, prepare all digests (sequential preprocessing)
        prepared_digests = []
        for i, digest_data in enumerate(digests, 1):
            try:
                digest, error_result = self._process_single_digest(digest_data, i, len(digests))
                if error_result:
                    audio_results.append(error_result)
                    continue
                prepared_digests.append((i, digest))
            except Exception as e:
                self.logger.error(f"Failed to process digest data: {e}")
                audio_results.append({
                    'success': False,
                    'error': str(e)
                })

        if not prepared_digests:
            return audio_results

        # Parallel processing
        self.logger.info(f"Processing {len(prepared_digests)} digests with up to {MAX_WORKERS} concurrent workers")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all tasks
            future_to_digest = {}
            for i, digest in prepared_digests:
                future = executor.submit(self._generate_audio_for_digest_with_timeout, digest, 60)
                future_to_digest[future] = (i, digest)

            # Process completed tasks as they finish
            completed_count = 0
            for future in as_completed(future_to_digest):
                i, digest = future_to_digest[future]
                completed_count += 1

                try:
                    result = future.result()
                    audio_results.append(result)

                    # Progress logging
                    status = "✅ Success" if result.get('success') else "❌ Failed"
                    if result.get('skipped'):
                        status = "⏭️ Skipped"

                    self.logger.info(f"[{completed_count}/{len(prepared_digests)}] {status}: {digest.topic}")

                except Exception as e:
                    self.logger.error(f"[{completed_count}/{len(prepared_digests)}] ❌ Exception: {digest.topic} - {e}")
                    audio_results.append({
                        'digest_id': digest.id,
                        'topic': digest.topic,
                        'success': False,
                        'error': str(e)
                    })

        return audio_results

    def _process_single_digest(self, digest_data, index, total):
        """Process and validate a single digest data entry. Returns (digest, error_result)"""
        if isinstance(digest_data, int):
            # Digest ID
            digest = self.digest_repo.get_by_id(digest_data)
            if not digest:
                self.logger.error(f"[{index}/{total}] Digest {digest_data} not found in database")
                return None, {
                    'digest_id': digest_data,
                    'success': False,
                    'error': 'Digest not found in database'
                }
        elif isinstance(digest_data, dict):
            # Digest data from previous phase
            if 'id' in digest_data:
                digest = self.digest_repo.get_by_id(digest_data['id'])
                if not digest:
                    self.logger.error(f"[{index}/{total}] Digest {digest_data['id']} not found in database")
                    return None, {
                        'digest_id': digest_data['id'],
                        'topic': digest_data.get('topic', 'unknown'),
                        'success': False,
                        'error': 'Digest not found in database'
                    }
            else:
                self.logger.error(f"[{index}/{total}] Invalid digest data format: missing 'id' field")
                return None, {
                    'success': False,
                    'error': 'Invalid digest data format'
                }
        else:
            # Assume it's a digest object
            digest = digest_data

        return digest, None

    def _generate_audio_for_digest_with_timeout(self, digest, timeout_seconds):
        """Generate audio for a digest with timeout protection"""
        start_time = time.time()
        try:
            result = self._generate_audio_for_digest(digest)
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds * 0.8:  # Warn if close to timeout
                self.logger.warning(f"TTS generation for {digest.topic} took {elapsed:.1f}s (close to {timeout_seconds}s timeout)")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            self.logger.error(f"TTS generation failed for {digest.topic} after {elapsed:.1f}s: {e}")
            return {
                'digest_id': digest.id,
                'topic': digest.topic,
                'success': False,
                'error': f"Timeout or error after {elapsed:.1f}s: {str(e)}"
            }

    def _generate_audio_for_digest(self, digest):
        """Generate audio for a single digest"""

        try:
            # Use CompleteAudioProcessor to handle TTS generation
            result = self.complete_audio_processor.process_digest_to_audio(digest)

            if result.get('skipped'):
                self.logger.info(f"   ⏭️  Skipped: {result.get('skip_reason')}")
                return {
                    'digest_id': digest.id,
                    'topic': digest.topic,
                    'success': True,
                    'skipped': True,
                    'skip_reason': result.get('skip_reason'),
                    'audio_metadata': None
                }
            elif result.get('success'):
                audio_metadata = result.get('audio_metadata')
                if audio_metadata:
                    # Handle both dict and object forms
                    if isinstance(audio_metadata, dict):
                        file_path = audio_metadata.get('file_path', 'Unknown')
                    else:
                        file_path = getattr(audio_metadata, 'file_path', 'Unknown')
                    file_name = Path(file_path).name if file_path != 'Unknown' else 'Unknown'
                    self.logger.info(f"   ✅ Generated successfully: {file_name}")
                else:
                    self.logger.info(f"   ✅ Generated successfully (no metadata)")

                return {
                    'digest_id': digest.id,
                    'topic': digest.topic,
                    'success': True,
                    'skipped': False,
                    'audio_metadata': serialize_for_json(audio_metadata)
                }
            else:
                errors = result.get('errors', ['Unknown error'])
                self.logger.error(f"   ❌ Failed: {errors[0]}")
                return {
                    'digest_id': digest.id,
                    'topic': digest.topic,
                    'success': False,
                    'skipped': False,
                    'errors': errors
                }

        except Exception as e:
            self.logger.error(f"Audio generation failed for {digest.topic}: {e}")
            return {
                'digest_id': digest.id,
                'topic': digest.topic,
                'success': False,
                'skipped': False,
                'errors': [str(e)]
            }

def main():
    parser = argparse.ArgumentParser(description='TTS Audio Generation Phase')
    parser.add_argument('input', nargs='?', help='(DEPRECATED - ignored) Input JSON file from digest phase or digest IDs')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be generated')
    parser.add_argument('--limit', type=int, help='Limit number of digests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    parser.add_argument('--output', help='Output JSON file (default: stdout)')

    args = parser.parse_args()

    dry_run = resolve_dry_run_flag(args.dry_run)

    try:
        runner = TTSRunner(
            dry_run=dry_run,
            limit=args.limit,
            verbose=args.verbose
        )

        # DEPRECATED: JSON input is no longer used - TTS phase reads directly from database
        if args.input:
            runner.logger.warning(f"JSON input '{args.input}' is deprecated and ignored - TTS phase reads directly from database")

        result = runner.generate_audio()

        # Serialize result for JSON output (handles datetime and dataclass objects)
        json_safe_result = serialize_for_json(result)

        # Output JSON
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(json_safe_result, f, indent=2)
        else:
            print(json.dumps(json_safe_result))
            sys.stdout.flush()

        # Exit code
        sys.exit(0 if result['success'] else 1)

    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e),
            'audio_generated': 0,
            'audio_results': []
        }

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(error_result, f, indent=2)
        else:
            print(json.dumps(error_result))
            sys.stdout.flush()

        sys.exit(1)

if __name__ == '__main__':
    main()