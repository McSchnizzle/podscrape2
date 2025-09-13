"""
Complete Audio Processor for RSS Podcast Transcript Digest System.
Integrates all Phase 6 components: TTS, metadata generation, and database updates.
"""

import os
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from .audio_generator import AudioGenerator, AudioMetadata
from .metadata_generator import MetadataGenerator, EpisodeMetadata
from .audio_manager import AudioManager
from ..database.models import Digest, get_digest_repo
from ..config.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class CompleteAudioProcessor:
    """
    Orchestrates the complete audio generation pipeline:
    Script → Metadata → TTS → Database Update → File Management
    """
    
    def __init__(self, config_manager: ConfigManager = None):
        self.config = config_manager or ConfigManager()
        
        # Initialize all Phase 6 components
        self.audio_generator = AudioGenerator(config_manager)
        self.metadata_generator = MetadataGenerator()
        self.audio_manager = AudioManager()
        self.digest_repo = get_digest_repo()
        
        logger.info("CompleteAudioProcessor initialized with all Phase 6 components")
    
    def process_digest_to_audio(self, digest: Digest) -> Dict[str, any]:
        """
        Process a digest through the complete audio pipeline.
        Returns processing results and metadata.
        """
        logger.info(f"Processing digest {digest.id} ({digest.topic}) to audio")
        
        results = {
            'digest_id': digest.id,
            'topic': digest.topic,
            'success': False,
            'metadata': None,
            'audio_metadata': None,
            'database_updated': False,
            'errors': []
        }
        
        try:
            # Step 1: Skip audio generation for no-content digests (episode_count = 0)
            if digest.episode_count == 0:
                logger.info(f"Skipping audio generation for no-content digest {digest.id} (topic: {digest.topic})")
                logger.info("No episodes scored ≥0.65 for this topic - no MP3 will be created")
                results['success'] = True  # Mark as successful skip
                results['skipped'] = True
                results['skip_reason'] = "No qualifying episodes (score < 0.65)"
                return results
            
            # Step 2: Check if audio already exists; if script is newer, regenerate
            if digest.mp3_path and Path(digest.mp3_path).exists():
                mp3_p = Path(digest.mp3_path)
                script_p = Path(digest.script_path) if digest.script_path else None
                try:
                    if script_p and script_p.exists() and script_p.stat().st_mtime > mp3_p.stat().st_mtime:
                        logger.info(
                            f"Existing audio is older than script (mp3: {mp3_p.stat().st_mtime}, script: {script_p.stat().st_mtime}); regenerating"
                        )
                    else:
                        logger.info(f"Audio already exists for digest {digest.id}: {digest.mp3_path}")
                        results['success'] = True
                        results['audio_metadata'] = {
                            'file_path': digest.mp3_path,
                            'title': digest.mp3_title,
                            'summary': digest.mp3_summary
                        }
                        return results
                except Exception:
                    # If stats fail, fall through to regenerate
                    logger.info("Could not compare timestamps; regenerating audio as a safe fallback")
            
            if not digest.script_path or not Path(digest.script_path).exists():
                error_msg = f"Script file not found for digest {digest.id}: {digest.script_path}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
                return results
            
            # Step 3: Generate episode metadata
            logger.info(f"Generating metadata for digest {digest.id}")
            try:
                episode_metadata = self.metadata_generator.generate_metadata_for_digest(digest)
                results['metadata'] = episode_metadata
                logger.info(f"Generated metadata: '{episode_metadata.title}'")
            except Exception as e:
                error_msg = f"Metadata generation failed: {e}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
                return results
            
            # Step 4: Generate TTS audio
            logger.info(f"Generating TTS audio for digest {digest.id}")
            try:
                # Extract timestamp from script filename to keep MP3 and script aligned
                import re as _re
                ts = None
                try:
                    m = _re.search(r"_(\d{8}_\d{6})\.md$", str(Path(digest.script_path).name))
                    if m:
                        ts = m.group(1)
                except Exception:
                    ts = None
                audio_metadata = self.audio_generator.generate_audio_for_script(
                    digest.script_path,
                    digest.topic,
                    timestamp=ts
                )
                results['audio_metadata'] = audio_metadata
                logger.info(f"Generated audio: {Path(audio_metadata.file_path).name}")
            except Exception as e:
                error_msg = f"TTS audio generation failed: {e}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
                return results
            
            # Step 5: Update database with audio metadata
            logger.info(f"Updating database for digest {digest.id}")
            try:
                self.digest_repo.update_audio(
                    digest_id=digest.id,
                    mp3_path=audio_metadata.file_path,
                    duration_seconds=int(audio_metadata.duration_seconds or 0),
                    title=episode_metadata.title,
                    summary=episode_metadata.summary
                )
                results['database_updated'] = True
                logger.info(f"Database updated for digest {digest.id}")
            except Exception as e:
                error_msg = f"Database update failed: {e}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
                return results
            
            # Step 5: Organize audio files
            try:
                self.audio_manager.organize_audio_files()
                logger.info("Audio files organized")
            except Exception as e:
                # Non-critical error
                logger.warning(f"Audio file organization failed: {e}")
            
            results['success'] = True
            logger.info(f"Successfully processed digest {digest.id} to audio")
            
        except Exception as e:
            error_msg = f"Unexpected error processing digest {digest.id}: {e}"
            results['errors'].append(error_msg)
            logger.error(error_msg)
        
        return results
    
    def process_digests_for_date(self, target_date: date) -> Dict[str, any]:
        """Process all digests for a specific date to audio"""
        logger.info(f"Processing all digests for {target_date} to audio")
        
        # Get all digests for the date
        digests = self.digest_repo.get_by_date(target_date)
        
        if not digests:
            logger.info(f"No digests found for {target_date}")
            return {
                'date': target_date,
                'total_digests': 0,
                'processed': 0,
                'successful': 0,
                'failed': 0,
                'results': []
            }
        
        logger.info(f"Found {len(digests)} digests for {target_date}")
        
        summary = {
            'date': target_date,
            'total_digests': len(digests),
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'results': []
        }
        
        for digest in digests:
            try:
                result = self.process_digest_to_audio(digest)
                summary['results'].append(result)
                summary['processed'] += 1
                
                if result['success']:
                    summary['successful'] += 1
                else:
                    summary['failed'] += 1
                    
            except Exception as e:
                logger.error(f"Failed to process digest {digest.id}: {e}")
                summary['failed'] += 1
                summary['results'].append({
                    'digest_id': digest.id,
                    'topic': digest.topic,
                    'success': False,
                    'errors': [f"Processing exception: {e}"]
                })
        
        logger.info(f"Completed processing for {target_date}: {summary['successful']}/{summary['total_digests']} successful")
        return summary
    
    def get_audio_ready_digests(self, target_date: date = None) -> List[Digest]:
        """Get digests that have been processed to audio"""
        if target_date:
            digests = self.digest_repo.get_by_date(target_date)
        else:
            digests = self.digest_repo.get_recent_digests(days=7)
        
        # Filter for digests with audio
        audio_ready = [
            d for d in digests 
            if d.mp3_path and Path(d.mp3_path).exists()
        ]
        
        logger.info(f"Found {len(audio_ready)} audio-ready digests")
        return audio_ready
    
    def validate_audio_integration(self) -> Dict[str, any]:
        """Validate the complete audio integration system"""
        validation = {
            'components': {},
            'database': {},
            'files': {},
            'overall_health': True
        }
        
        try:
            # Test component initialization
            validation['components'] = {
                'audio_generator': self.audio_generator is not None,
                'metadata_generator': self.metadata_generator is not None,
                'audio_manager': self.audio_manager is not None,
                'digest_repo': self.digest_repo is not None
            }
            
            # Test database connectivity
            try:
                recent_digests = self.digest_repo.get_recent_digests(days=1)
                validation['database'] = {
                    'connection': True,
                    'recent_digests_count': len(recent_digests),
                    'has_digests_with_audio': sum(1 for d in recent_digests if d.mp3_path) > 0
                }
            except Exception as e:
                validation['database'] = {
                    'connection': False,
                    'error': str(e)
                }
                validation['overall_health'] = False
            
            # Test file system
            audio_files = self.audio_manager.get_audio_files("current")
            validation['files'] = {
                'audio_directory_exists': self.audio_manager.current_dir.exists(),
                'current_audio_files': len(audio_files),
                'storage_stats': self.audio_manager.get_storage_stats()
            }
            
            # Overall health check
            component_health = all(validation['components'].values())
            database_health = validation['database'].get('connection', False)
            file_health = validation['files']['audio_directory_exists']
            
            validation['overall_health'] = component_health and database_health and file_health
            
        except Exception as e:
            validation['overall_health'] = False
            validation['validation_error'] = str(e)
        
        return validation
    
    def generate_processing_report(self, results: Dict[str, any]) -> str:
        """Generate a human-readable processing report"""
        if 'date' in results:
            # Date-based processing report
            report = f"""
📊 Audio Processing Report for {results['date']}
{'=' * 50}

📈 Summary:
   Total digests: {results['total_digests']}
   Processed: {results['processed']}
   Successful: {results['successful']}
   Failed: {results['failed']}
   Success rate: {(results['successful']/results['total_digests']*100):.1f}%

📋 Details:"""
            
            for result in results['results']:
                status = "✅" if result['success'] else "❌"
                report += f"\n   {status} {result['topic']} (Digest {result['digest_id']})"
                
                if result.get('errors'):
                    for error in result['errors']:
                        report += f"\n      Error: {error}"
                        
                if result.get('audio_metadata'):
                    am = result['audio_metadata']
                    if isinstance(am, dict):
                        report += f"\n      Audio: {Path(am.get('file_path', '')).name}"
                    else:
                        report += f"\n      Audio: {Path(am.file_path).name}"
        else:
            # Single digest report
            status = "✅" if results['success'] else "❌"
            report = f"""
📊 Audio Processing Report for Digest {results['digest_id']}
{'=' * 55}

{status} Status: {'SUCCESS' if results['success'] else 'FAILED'}
🎯 Topic: {results['topic']}

"""
            if results.get('metadata'):
                meta = results['metadata']
                report += f"📝 Generated Title: '{meta.title}'\n"
                report += f"📄 Summary: {meta.summary[:80]}...\n"
            
            if results.get('audio_metadata'):
                am = results['audio_metadata']
                if isinstance(am, dict):
                    report += f"🔊 Audio File: {Path(am.get('file_path', '')).name}\n"
                else:
                    report += f"🔊 Audio File: {Path(am.file_path).name}\n"
                    report += f"⏱️ Duration: {am.duration_seconds:.1f} seconds\n"
            
            if results.get('errors'):
                report += "\n❌ Errors:\n"
                for error in results['errors']:
                    report += f"   • {error}\n"
        
        return report
