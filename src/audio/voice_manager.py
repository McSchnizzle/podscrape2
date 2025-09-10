"""
Voice Manager for ElevenLabs TTS Integration.
Handles voice configuration, selection, and ElevenLabs API interaction.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

@dataclass
class Voice:
    """ElevenLabs voice configuration"""
    voice_id: str
    name: str
    category: str = "premade"
    description: str = ""
    preview_url: str = ""

@dataclass
class VoiceSettings:
    """ElevenLabs voice generation settings"""
    stability: float = 0.75
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True

class VoiceManager:
    """
    Manages ElevenLabs voice configuration and API interaction.
    Handles voice discovery, topic mapping, and settings management.
    """
    
    def __init__(self):
        # Load environment variables to ensure API key is available
        load_dotenv()
        self.api_key = os.getenv('ELEVENLABS_API_KEY')
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY environment variable is required")
        
        self.base_url = "https://api.elevenlabs.io/v1"
        self.headers = {
            "Accept": "application/json",
            "xi-api-key": self.api_key
        }
        
        # Initialize voice cache
        self._available_voices: Optional[List[Voice]] = None
        self._topic_voice_mapping: Dict[str, str] = {}
        
        # Load default settings
        self.default_settings = VoiceSettings()
        
    def get_available_voices(self, refresh: bool = False) -> List[Voice]:
        """Get available ElevenLabs voices"""
        if self._available_voices is None or refresh:
            self._fetch_available_voices()
        return self._available_voices or []
    
    def _fetch_available_voices(self) -> None:
        """Fetch voices from ElevenLabs API"""
        try:
            response = requests.get(
                f"{self.base_url}/voices",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            
            voices_data = response.json()
            self._available_voices = []
            
            for voice_data in voices_data.get('voices', []):
                voice = Voice(
                    voice_id=voice_data['voice_id'],
                    name=voice_data['name'],
                    category=voice_data.get('category', 'premade'),
                    description=voice_data.get('description', ''),
                    preview_url=voice_data.get('preview_url', '')
                )
                self._available_voices.append(voice)
            
            logger.info(f"Fetched {len(self._available_voices)} available voices")
            
        except Exception as e:
            logger.error(f"Failed to fetch available voices: {e}")
            # Set empty list as fallback
            self._available_voices = []
    
    def get_recommended_voices_for_topics(self) -> Dict[str, str]:
        """Get recommended voice mappings for each topic based on voice characteristics"""
        voices = self.get_available_voices()
        
        if not voices:
            logger.warning("No voices available, using placeholder IDs")
            return {
                "AI News": "placeholder_ai_voice",
                "Tech News and Tech Culture": "placeholder_tech_voice", 
                "Community Organizing": "placeholder_community_voice",
                "Societal Culture Change": "placeholder_culture_voice"
            }
        
        # Find suitable voices for each topic
        recommendations = {}
        
        # Look for specific voice characteristics
        male_voices = [v for v in voices if 'male' in v.name.lower() or 'man' in v.name.lower()]
        female_voices = [v for v in voices if 'female' in v.name.lower() or 'woman' in v.name.lower()]
        neutral_voices = [v for v in voices if v not in male_voices and v not in female_voices]
        
        # Default to first available voices if we can't find specific categories
        available_voices = voices[:4] if len(voices) >= 4 else voices
        
        topic_voice_map = [
            ("AI News", "tech-focused, clear voice"),
            ("Tech News and Tech Culture", "professional, engaging voice"),
            ("Community Organizing", "warm, inspiring voice"), 
            ("Societal Culture Change", "thoughtful, authoritative voice")
        ]
        
        for i, (topic, description) in enumerate(topic_voice_map):
            if i < len(available_voices):
                recommendations[topic] = available_voices[i].voice_id
                logger.info(f"Mapped '{topic}' to voice '{available_voices[i].name}' ({description})")
            else:
                recommendations[topic] = f"placeholder_voice_{i+1}"
                logger.warning(f"No voice available for '{topic}', using placeholder")
        
        return recommendations
    
    def update_topic_voice_configuration(self, config_path: str = "config/topics.json") -> bool:
        """Update topics.json with real ElevenLabs voice IDs"""
        try:
            # Get recommended voice mappings
            voice_mappings = self.get_recommended_voices_for_topics()
            
            # Read existing configuration
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Update voice IDs for each topic
            updated_count = 0
            for topic in config.get('topics', []):
                topic_name = topic['name']
                if topic_name in voice_mappings:
                    old_voice_id = topic.get('voice_id', '')
                    new_voice_id = voice_mappings[topic_name]
                    
                    if old_voice_id != new_voice_id:
                        topic['voice_id'] = new_voice_id
                        updated_count += 1
                        logger.info(f"Updated voice for '{topic_name}': {old_voice_id} → {new_voice_id}")
            
            # Update voice settings if they don't exist
            if 'default_voice_settings' not in config.get('settings', {}):
                if 'settings' not in config:
                    config['settings'] = {}
                
                config['settings']['default_voice_settings'] = {
                    'stability': self.default_settings.stability,
                    'similarity_boost': self.default_settings.similarity_boost,
                    'style': self.default_settings.style,
                    'use_speaker_boost': self.default_settings.use_speaker_boost
                }
                logger.info("Added default voice settings to configuration")
            
            # Update last_updated timestamp
            from datetime import datetime
            config['last_updated'] = datetime.now().isoformat()
            
            # Write updated configuration
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Updated topic configuration with {updated_count} voice changes")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update topic voice configuration: {e}")
            return False
    
    def get_voice_by_id(self, voice_id: str) -> Optional[Voice]:
        """Get voice details by ID"""
        voices = self.get_available_voices()
        return next((v for v in voices if v.voice_id == voice_id), None)
    
    def validate_voice_configuration(self, config_path: str = "config/topics.json") -> Dict[str, Any]:
        """Validate that all configured voices are available"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            results = {
                'valid': True,
                'issues': [],
                'topics_checked': 0,
                'voices_available': len(self.get_available_voices())
            }
            
            for topic in config.get('topics', []):
                if not topic.get('active', True):
                    continue
                
                results['topics_checked'] += 1
                topic_name = topic['name']
                voice_id = topic.get('voice_id', '')
                
                if not voice_id or voice_id.startswith('placeholder') or voice_id.startswith('elevenlabs_voice_id'):
                    results['valid'] = False
                    results['issues'].append(f"Topic '{topic_name}' has placeholder voice ID: {voice_id}")
                    continue
                
                voice = self.get_voice_by_id(voice_id)
                if not voice:
                    results['valid'] = False
                    results['issues'].append(f"Topic '{topic_name}' voice ID '{voice_id}' not found in available voices")
                else:
                    logger.info(f"✅ Topic '{topic_name}' mapped to valid voice '{voice.name}'")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to validate voice configuration: {e}")
            return {
                'valid': False,
                'issues': [f"Configuration validation error: {e}"],
                'topics_checked': 0,
                'voices_available': 0
            }
    
    def get_voice_settings_for_topic(self, topic_name: str, config_path: str = "config/topics.json") -> VoiceSettings:
        """Get voice settings for a specific topic"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Look for topic-specific settings
            for topic in config.get('topics', []):
                if topic['name'] == topic_name:
                    topic_settings = topic.get('voice_settings', {})
                    if topic_settings:
                        return VoiceSettings(**topic_settings)
            
            # Fall back to default settings
            default_settings = config.get('settings', {}).get('default_voice_settings', {})
            return VoiceSettings(**default_settings)
            
        except Exception as e:
            logger.error(f"Failed to get voice settings for topic '{topic_name}': {e}")
            return self.default_settings