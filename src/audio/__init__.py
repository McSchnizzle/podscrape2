"""
Audio module for RSS Podcast Transcript Digest System.
Handles TTS generation and voice management.
"""

from .voice_manager import VoiceManager, Voice, VoiceSettings
from .audio_generator import AudioGenerator, AudioMetadata, AudioGenerationError
from .metadata_generator import MetadataGenerator, EpisodeMetadata, MetadataGenerationError
from .audio_manager import AudioManager, AudioFileInfo
from .complete_audio_processor import CompleteAudioProcessor

__all__ = [
    'VoiceManager', 'Voice', 'VoiceSettings',
    'AudioGenerator', 'AudioMetadata', 'AudioGenerationError',
    'MetadataGenerator', 'EpisodeMetadata', 'MetadataGenerationError',
    'AudioManager', 'AudioFileInfo',
    'CompleteAudioProcessor'
]