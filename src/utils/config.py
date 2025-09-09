"""
Configuration management for YouTube Transcript Digest System.
Handles loading and validation of channels.json and topics.json configuration files.
"""

import json
import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class TopicConfig:
    """Configuration for a single topic"""
    name: str
    instruction_file: str
    voice_id: str
    active: bool = True
    description: Optional[str] = None
    
    def __post_init__(self):
        """Validate topic configuration"""
        if not self.name:
            raise ValueError("Topic name cannot be empty")
        if not self.instruction_file:
            raise ValueError("Topic instruction_file cannot be empty")
        if not self.voice_id:
            raise ValueError("Topic voice_id cannot be empty")

@dataclass
class ChannelConfig:
    """Configuration for a single YouTube channel"""
    name: str
    channel_id: str
    url: str
    active: bool = True
    added_date: Optional[str] = None
    description: Optional[str] = None
    
    def __post_init__(self):
        """Validate channel configuration"""
        if not self.name:
            raise ValueError("Channel name cannot be empty")
        if not self.channel_id:
            raise ValueError("Channel channel_id cannot be empty")
        if not self.url:
            raise ValueError("Channel url cannot be empty")
        
        # Set added_date if not provided
        if self.added_date is None:
            self.added_date = datetime.now().isoformat()

class ConfigManager:
    """
    Manages configuration files for the YouTube Digest System.
    Handles loading, validation, and saving of channels.json and topics.json.
    """
    
    def __init__(self, config_dir: str = None):
        if config_dir is None:
            # Default to config/ directory relative to project root
            project_root = Path(__file__).parent.parent.parent
            config_dir = project_root / 'config'
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        self.channels_file = self.config_dir / 'channels.json'
        self.topics_file = self.config_dir / 'topics.json'
        
        # Initialize config files if they don't exist
        self._ensure_config_files_exist()
    
    def _ensure_config_files_exist(self):
        """Create default configuration files if they don't exist"""
        
        # Create default topics.json
        if not self.topics_file.exists():
            default_topics = {
                "topics": [
                    {
                        "name": "AI News",
                        "instruction_file": "AI News.md",
                        "voice_id": "elevenlabs_voice_id_1",
                        "active": True,
                        "description": "AI developments, machine learning breakthroughs, AI product launches"
                    },
                    {
                        "name": "Tech News and Tech Culture",
                        "instruction_file": "Tech News and Tech Culture.md", 
                        "voice_id": "elevenlabs_voice_id_2",
                        "active": True,
                        "description": "Technology industry news, tech company developments, digital culture"
                    },
                    {
                        "name": "Community Organizing",
                        "instruction_file": "Community Organizing.md",
                        "voice_id": "elevenlabs_voice_id_3",
                        "active": True,
                        "description": "Community organizing strategies, grassroots movements, activism"
                    },
                    {
                        "name": "Societal Culture Change",
                        "instruction_file": "Societal Culture Change.md",
                        "voice_id": "elevenlabs_voice_id_4",
                        "active": True,
                        "description": "Social movements, cultural shifts, societal transformation"
                    }
                ],
                "settings": {
                    "score_threshold": 0.65,
                    "max_words_per_script": 25000,
                    "default_voice_settings": {
                        "stability": 0.75,
                        "similarity_boost": 0.75,
                        "style": 0.0,
                        "use_speaker_boost": True
                    }
                },
                "last_updated": datetime.now().isoformat()
            }
            
            with open(self.topics_file, 'w') as f:
                json.dump(default_topics, f, indent=2)
            
            logger.info(f"Created default topics configuration: {self.topics_file}")
        
        # Create default channels.json
        if not self.channels_file.exists():
            default_channels = {
                "channels": [],
                "settings": {
                    "min_video_duration_seconds": 180,  # 3 minutes
                    "max_concurrent_fetches": 5,
                    "retry_attempts": 3,
                    "failure_threshold": 3,  # Flag channel after 3 consecutive failures
                    "check_frequency_hours": 6
                },
                "last_updated": datetime.now().isoformat()
            }
            
            with open(self.channels_file, 'w') as f:
                json.dump(default_channels, f, indent=2)
            
            logger.info(f"Created default channels configuration: {self.channels_file}")
    
    def load_topics(self) -> List[TopicConfig]:
        """Load and validate topics configuration"""
        try:
            with open(self.topics_file, 'r') as f:
                data = json.load(f)
            
            topics = []
            for topic_data in data.get('topics', []):
                topics.append(TopicConfig(**topic_data))
            
            logger.info(f"Loaded {len(topics)} topics from configuration")
            return topics
            
        except FileNotFoundError:
            logger.error(f"Topics configuration file not found: {self.topics_file}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in topics configuration: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to load topics configuration: {e}")
            return []
    
    def load_channels(self) -> List[ChannelConfig]:
        """Load and validate channels configuration"""
        try:
            with open(self.channels_file, 'r') as f:
                data = json.load(f)
            
            channels = []
            for channel_data in data.get('channels', []):
                channels.append(ChannelConfig(**channel_data))
            
            logger.info(f"Loaded {len(channels)} channels from configuration")
            return channels
            
        except FileNotFoundError:
            logger.error(f"Channels configuration file not found: {self.channels_file}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in channels configuration: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to load channels configuration: {e}")
            return []
    
    def save_channels(self, channels: List[ChannelConfig]):
        """Save channels configuration to file"""
        try:
            # Load existing data to preserve settings
            existing_data = {}
            if self.channels_file.exists():
                with open(self.channels_file, 'r') as f:
                    existing_data = json.load(f)
            
            # Update channels data
            data = {
                "channels": [asdict(channel) for channel in channels],
                "settings": existing_data.get('settings', {}),
                "last_updated": datetime.now().isoformat()
            }
            
            with open(self.channels_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(channels)} channels to configuration")
            
        except Exception as e:
            logger.error(f"Failed to save channels configuration: {e}")
            raise
    
    def save_topics(self, topics: List[TopicConfig]):
        """Save topics configuration to file"""
        try:
            # Load existing data to preserve settings
            existing_data = {}
            if self.topics_file.exists():
                with open(self.topics_file, 'r') as f:
                    existing_data = json.load(f)
            
            # Update topics data
            data = {
                "topics": [asdict(topic) for topic in topics],
                "settings": existing_data.get('settings', {}),
                "last_updated": datetime.now().isoformat()
            }
            
            with open(self.topics_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(topics)} topics to configuration")
            
        except Exception as e:
            logger.error(f"Failed to save topics configuration: {e}")
            raise
    
    def get_topic_config(self, topic_name: str) -> Optional[TopicConfig]:
        """Get configuration for a specific topic"""
        topics = self.load_topics()
        for topic in topics:
            if topic.name == topic_name:
                return topic
        return None
    
    def get_channel_config(self, channel_id: str) -> Optional[ChannelConfig]:
        """Get configuration for a specific channel"""
        channels = self.load_channels()
        for channel in channels:
            if channel.channel_id == channel_id:
                return channel
        return None
    
    def add_channel(self, name: str, channel_id: str, url: str, description: str = None) -> bool:
        """Add a new channel to configuration"""
        try:
            channels = self.load_channels()
            
            # Check if channel already exists
            if any(c.channel_id == channel_id for c in channels):
                logger.warning(f"Channel {channel_id} already exists in configuration")
                return False
            
            # Add new channel
            new_channel = ChannelConfig(
                name=name,
                channel_id=channel_id,
                url=url,
                description=description
            )
            
            channels.append(new_channel)
            self.save_channels(channels)
            
            logger.info(f"Added channel: {name} ({channel_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add channel: {e}")
            return False
    
    def remove_channel(self, channel_id: str) -> bool:
        """Remove a channel from configuration"""
        try:
            channels = self.load_channels()
            original_count = len(channels)
            
            channels = [c for c in channels if c.channel_id != channel_id]
            
            if len(channels) == original_count:
                logger.warning(f"Channel {channel_id} not found in configuration")
                return False
            
            self.save_channels(channels)
            logger.info(f"Removed channel: {channel_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove channel: {e}")
            return False
    
    def get_settings(self, config_type: str) -> Dict[str, Any]:
        """Get settings from configuration file"""
        try:
            if config_type == 'topics':
                with open(self.topics_file, 'r') as f:
                    data = json.load(f)
            elif config_type == 'channels':
                with open(self.channels_file, 'r') as f:
                    data = json.load(f)
            else:
                raise ValueError(f"Unknown config type: {config_type}")
            
            return data.get('settings', {})
            
        except Exception as e:
            logger.error(f"Failed to get {config_type} settings: {e}")
            return {}
    
    def validate_instruction_files(self) -> List[str]:
        """Validate that all topic instruction files exist"""
        missing_files = []
        
        # Get digest_instructions directory
        project_root = Path(__file__).parent.parent.parent
        instructions_dir = project_root / 'digest_instructions'
        
        topics = self.load_topics()
        for topic in topics:
            if topic.active:
                instruction_path = instructions_dir / topic.instruction_file
                if not instruction_path.exists():
                    missing_files.append(f"{topic.name}: {topic.instruction_file}")
        
        if missing_files:
            logger.warning(f"Missing instruction files: {missing_files}")
        
        return missing_files

def get_config_manager(config_dir: str = None) -> ConfigManager:
    """Factory function to get configuration manager"""
    return ConfigManager(config_dir)

# Environment variable helpers
def get_env_var(key: str, default: str = None, required: bool = True) -> str:
    """Get environment variable with validation"""
    value = os.getenv(key, default)
    
    if required and not value:
        raise ValueError(f"Required environment variable {key} is not set")
    
    return value

def load_api_keys() -> Dict[str, str]:
    """Load API keys from environment variables"""
    return {
        'openai_api_key': get_env_var('OPENAI_API_KEY'),
        'elevenlabs_api_key': get_env_var('ELEVENLABS_API_KEY'),
        'github_token': get_env_var('GITHUB_TOKEN'),
        'github_repository': get_env_var('GITHUB_REPOSITORY', 'McSchnizzle/podscrape2'),
    }

def validate_environment() -> bool:
    """Validate that all required environment variables are set"""
    required_vars = [
        'OPENAI_API_KEY',
        'ELEVENLABS_API_KEY', 
        'GITHUB_TOKEN'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return False
    
    logger.info("All required environment variables are set")
    return True