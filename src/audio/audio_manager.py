"""
Audio Manager for RSS Podcast Transcript Digest System.
Comprehensive audio file management, organization, and metadata handling.
"""

import os
import json
import shutil
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class AudioFileInfo:
    """Audio file information and metadata"""
    filename: str
    filepath: str
    topic: str
    date_created: datetime
    file_size_bytes: int
    estimated_duration_seconds: float
    voice_id: str
    voice_name: str

class AudioManager:
    """
    Manages audio file organization, cleanup, and metadata for the podcast system.
    Provides utilities for file management, cleanup, and archival.
    """
    
    def __init__(self, base_audio_dir: str = "data/completed-tts"):
        self.base_audio_dir = Path(base_audio_dir)
        self.base_audio_dir.mkdir(exist_ok=True)
        
        # Create subdirectories for organization
        self.current_dir = self.base_audio_dir / "current"
        self.archive_dir = self.base_audio_dir / "archive"
        self.temp_dir = self.base_audio_dir / "temp"
        
        self.current_dir.mkdir(exist_ok=True)
        self.archive_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
    
    def get_audio_files(self, directory: str = "current") -> List[AudioFileInfo]:
        """Get list of audio files with metadata"""
        target_dir = self._get_directory(directory)
        audio_files = []
        
        for audio_file in target_dir.glob("*.mp3"):
            try:
                file_info = self._parse_audio_filename(audio_file)
                if file_info:
                    audio_files.append(file_info)
            except Exception as e:
                logger.warning(f"Could not parse audio file {audio_file.name}: {e}")
                continue
        
        # Sort by creation date, newest first
        audio_files.sort(key=lambda x: x.date_created, reverse=True)
        return audio_files
    
    def _get_directory(self, directory: str) -> Path:
        """Get directory path by name"""
        if directory == "current":
            return self.current_dir
        elif directory == "archive":
            return self.archive_dir
        elif directory == "temp":
            return self.temp_dir
        elif directory == "base":
            return self.base_audio_dir
        else:
            return self.base_audio_dir / directory
    
    def _parse_audio_filename(self, audio_file: Path) -> Optional[AudioFileInfo]:
        """Parse audio filename to extract metadata"""
        filename = audio_file.name
        stem = audio_file.stem  # filename without extension
        
        # Expected format: Topic_Name_YYYYMMDD_HHMMSS.mp3
        parts = stem.split('_')
        
        if len(parts) < 3:
            logger.warning(f"Unexpected filename format: {filename}")
            return None
        
        try:
            # Extract date and time (last two parts)
            time_part = parts[-1]  # HHMMSS
            date_part = parts[-2]  # YYYYMMDD
            topic_parts = parts[:-2]  # Everything before date and time
            
            # Parse date and time
            date_str = f"{date_part}_{time_part}"
            date_created = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
            
            # Reconstruct topic name
            topic = ' '.join(topic_parts).replace('_', ' ')
            
            # Get file stats
            stat = audio_file.stat()
            
            return AudioFileInfo(
                filename=filename,
                filepath=str(audio_file),
                topic=topic,
                date_created=date_created,
                file_size_bytes=stat.st_size,
                estimated_duration_seconds=0.0,  # Would need audio analysis for accurate duration
                voice_id="unknown",
                voice_name="unknown"
            )
            
        except ValueError as e:
            logger.warning(f"Could not parse date from filename {filename}: {e}")
            return None
    
    def organize_audio_files(self) -> Dict[str, int]:
        """Organize audio files by moving them to appropriate directories"""
        results = {
            'moved_to_current': 0,
            'already_organized': 0,
            'errors': 0
        }
        
        # Move files from base directory to current
        for audio_file in self.base_audio_dir.glob("*.mp3"):
            if audio_file.parent == self.base_audio_dir:
                try:
                    target_path = self.current_dir / audio_file.name
                    if not target_path.exists():
                        shutil.move(str(audio_file), str(target_path))
                        results['moved_to_current'] += 1
                        logger.info(f"Moved {audio_file.name} to current directory")
                    else:
                        results['already_organized'] += 1
                except Exception as e:
                    logger.error(f"Failed to move {audio_file.name}: {e}")
                    results['errors'] += 1
        
        return results
    
    def archive_old_files(self, days_old: int = 7) -> Dict[str, int]:
        """Archive audio files older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        results = {
            'archived': 0,
            'errors': 0,
            'skipped': 0
        }
        
        current_files = self.get_audio_files("current")
        
        for file_info in current_files:
            if file_info.date_created < cutoff_date:
                try:
                    source_path = Path(file_info.filepath)
                    target_path = self.archive_dir / source_path.name
                    
                    if not target_path.exists():
                        shutil.move(str(source_path), str(target_path))
                        results['archived'] += 1
                        logger.info(f"Archived {source_path.name}")
                    else:
                        results['skipped'] += 1
                        logger.info(f"Archive file already exists: {target_path.name}")
                except Exception as e:
                    logger.error(f"Failed to archive {file_info.filename}: {e}")
                    results['errors'] += 1
        
        return results
    
    def cleanup_temp_files(self) -> int:
        """Clean up temporary files"""
        cleaned_count = 0
        
        for temp_file in self.temp_dir.glob("*"):
            try:
                if temp_file.is_file():
                    temp_file.unlink()
                    cleaned_count += 1
                    logger.info(f"Deleted temp file: {temp_file.name}")
            except Exception as e:
                logger.error(f"Failed to delete temp file {temp_file.name}: {e}")
        
        return cleaned_count
    
    def get_storage_stats(self) -> Dict[str, any]:
        """Get storage statistics for audio files"""
        stats = {
            'directories': {},
            'total_files': 0,
            'total_size_bytes': 0,
            'total_size_mb': 0.0
        }
        
        for dir_name in ['current', 'archive', 'temp', 'base']:
            directory = self._get_directory(dir_name)
            files = list(directory.glob("*.mp3"))
            
            dir_size = sum(f.stat().st_size for f in files if f.is_file())
            
            stats['directories'][dir_name] = {
                'file_count': len(files),
                'size_bytes': dir_size,
                'size_mb': dir_size / (1024 * 1024)
            }
            
            stats['total_files'] += len(files)
            stats['total_size_bytes'] += dir_size
        
        stats['total_size_mb'] = stats['total_size_bytes'] / (1024 * 1024)
        
        return stats
    
    def generate_filename(self, topic: str, timestamp: datetime = None) -> str:
        """Generate standardized filename for audio files"""
        if timestamp is None:
            timestamp = datetime.now()
        
        # Clean topic name for filename
        safe_topic = topic.replace(' ', '_').replace('&', 'and').replace('/', '_')
        safe_topic = ''.join(c for c in safe_topic if c.isalnum() or c in ['_', '-'])
        
        # Generate timestamp
        date_str = timestamp.strftime('%Y%m%d_%H%M%S')
        
        return f"{safe_topic}_{date_str}.mp3"
    
    def validate_filename(self, filename: str) -> bool:
        """Validate that filename follows expected format"""
        try:
            stem = Path(filename).stem
            parts = stem.split('_')
            
            if len(parts) < 3:
                return False
            
            # Check if last two parts are date and time
            time_part = parts[-1]  # Should be HHMMSS
            date_part = parts[-2]  # Should be YYYYMMDD
            
            # Validate date format
            datetime.strptime(f"{date_part}_{time_part}", "%Y%m%d_%H%M%S")
            
            return True
            
        except (ValueError, IndexError):
            return False
    
    def get_files_by_topic(self, topic: str, directory: str = "current") -> List[AudioFileInfo]:
        """Get all audio files for a specific topic"""
        all_files = self.get_audio_files(directory)
        return [f for f in all_files if f.topic.lower() == topic.lower()]
    
    def get_files_by_date_range(self, start_date: date, end_date: date, 
                               directory: str = "current") -> List[AudioFileInfo]:
        """Get audio files within a date range"""
        all_files = self.get_audio_files(directory)
        
        return [
            f for f in all_files 
            if start_date <= f.date_created.date() <= end_date
        ]
    
    def export_metadata(self, output_file: str = "audio_metadata.json") -> str:
        """Export audio file metadata to JSON"""
        metadata = {
            'export_date': datetime.now().isoformat(),
            'storage_stats': self.get_storage_stats(),
            'files': {
                'current': [asdict(f) for f in self.get_audio_files("current")],
                'archive': [asdict(f) for f in self.get_audio_files("archive")]
            }
        }
        
        output_path = self.base_audio_dir / output_file
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        logger.info(f"Exported metadata to {output_path}")
        return str(output_path)