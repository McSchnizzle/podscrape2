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
from datetime import datetime
from pathlib import Path
import argparse
from dataclasses import asdict, is_dataclass

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

# Set up environment
from dotenv import load_dotenv
load_dotenv()
from src.config.env import require_database_url
require_database_url()

from src.database.models import get_digest_repo
from src.audio.complete_audio_processor import CompleteAudioProcessor

def serialize_audio_metadata(obj):
    """Convert dataclass objects to dictionaries for JSON serialization"""
    if is_dataclass(obj):
        return asdict(obj)
    return obj

class TTSRunner:
    """TTS audio generation phase"""

    def __init__(self, dry_run: bool = False, limit: int = None, verbose: bool = False):
        # Configure logging
        self.logger = logging.getLogger(__name__)
        level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')

        self.dry_run = dry_run
        self.limit = limit
        self.verbose = verbose

        # Initialize repositories and components
        self.digest_repo = get_digest_repo()
        self.complete_audio_processor = CompleteAudioProcessor()

        # Verify API keys
        self._verify_dependencies()

        self.logger.info("TTS audio generation initialized")

    def _verify_dependencies(self):
        """Verify required dependencies"""
        self.logger.info("Verifying dependencies...")

        # Check ElevenLabs API key
        elevenlabs_key = os.getenv('ELEVENLABS_API_KEY')
        if not elevenlabs_key or elevenlabs_key.startswith('test-') or elevenlabs_key == 'your-key-here':
            self.logger.warning("ElevenLabs API key not configured - TTS may not work")
        else:
            self.logger.info("✓ ElevenLabs API key configured")

    def generate_audio(self, digests_data):
        """Generate TTS audio from digest phase or direct digest data"""

        if isinstance(digests_data, str):
            # Load from JSON file
            with open(digests_data, 'r') as f:
                data = json.load(f)
            if not data.get('success', False):
                return {
                    'success': False,
                    'error': f"Digest phase failed: {data.get('error', 'Unknown error')}",
                    'audio_generated': 0,
                    'audio_results': []
                }
            digests = data.get('digests', [])
        elif isinstance(digests_data, dict):
            # Direct JSON data
            if not digests_data.get('success', False):
                return {
                    'success': False,
                    'error': f"Digest phase failed: {digests_data.get('error', 'Unknown error')}",
                    'audio_generated': 0,
                    'audio_results': []
                }
            digests = digests_data.get('digests', [])
        elif isinstance(digests_data, list):
            # Direct list of digest IDs or digest objects
            digests = digests_data
        else:
            return {
                'success': False,
                'error': "Invalid input format - expected JSON file path, dict, or list",
                'audio_generated': 0,
                'audio_results': []
            }

        if not digests:
            return {
                'success': True,
                'audio_generated': 0,
                'audio_results': [],
                'message': "No digests to process for audio generation"
            }

        # Apply limit
        if self.limit:
            digests = digests[:self.limit]

        self.logger.info(f"Generating audio for {len(digests)} digests")

        audio_results = []

        for i, digest_data in enumerate(digests, 1):
            try:
                # Handle different digest data formats
                if isinstance(digest_data, int):
                    # Digest ID
                    digest = self.digest_repo.get_by_id(digest_data)
                    if not digest:
                        self.logger.error(f"Digest {digest_data} not found in database")
                        audio_results.append({
                            'digest_id': digest_data,
                            'success': False,
                            'error': 'Digest not found in database'
                        })
                        continue
                elif isinstance(digest_data, dict):
                    # Digest data from previous phase
                    if 'id' in digest_data:
                        digest = self.digest_repo.get_by_id(digest_data['id'])
                        if not digest:
                            self.logger.error(f"Digest {digest_data['id']} not found in database")
                            audio_results.append({
                                'digest_id': digest_data['id'],
                                'topic': digest_data.get('topic', 'unknown'),
                                'success': False,
                                'error': 'Digest not found in database'
                            })
                            continue
                    else:
                        self.logger.error(f"Invalid digest data format: missing 'id' field")
                        audio_results.append({
                            'success': False,
                            'error': 'Invalid digest data format'
                        })
                        continue
                else:
                    # Assume it's a digest object
                    digest = digest_data

                self.logger.info(f"\n[{i}/{len(digests)}] Generating audio: {digest.topic}")

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

        return {
            'success': len(failed) == 0,
            'audio_generated': len(successful),
            'audio_skipped': len(skipped),
            'audio_failed': len(failed),
            'audio_results': audio_results
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
                    'audio_metadata': serialize_audio_metadata(audio_metadata)
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
    parser.add_argument('input', nargs='?', help='Input JSON file from digest phase, digest ID, or digest IDs (comma-separated)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be generated')
    parser.add_argument('--limit', type=int, help='Limit number of digests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    parser.add_argument('--output', help='Output JSON file (default: stdout)')

    args = parser.parse_args()

    try:
        runner = TTSRunner(
            dry_run=args.dry_run,
            limit=args.limit,
            verbose=args.verbose
        )

        # Handle input
        if args.input:
            if args.input.endswith('.json') or '/' in args.input:
                # JSON file input
                digests_data = args.input
            elif ',' in args.input:
                # Comma-separated digest IDs
                ids = [int(id_str.strip()) for id_str in args.input.split(',')]
                digests_data = ids
            else:
                # Single digest ID
                try:
                    digests_data = [int(args.input)]
                except ValueError:
                    raise ValueError(f"Invalid digest ID: {args.input}")
        else:
            # Read from stdin
            digests_data = json.load(sys.stdin)

        result = runner.generate_audio(digests_data)

        # Output JSON
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
        else:
            print(json.dumps(result, indent=2))

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
            print(json.dumps(error_result, indent=2))

        sys.exit(1)

if __name__ == '__main__':
    main()