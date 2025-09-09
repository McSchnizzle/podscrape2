"""
Configuration Manager for RSS Podcast Transcript Digest System.
Provides centralized access to application configuration.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages application configuration from JSON files"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self._topics_config = None
        
    def _load_topics_config(self) -> Dict[str, Any]:
        """Load topics configuration from JSON file"""
        if self._topics_config is None:
            topics_path = self.config_dir / "topics.json"
            
            if not topics_path.exists():
                raise FileNotFoundError(f"Topics config not found: {topics_path}")
            
            try:
                with open(topics_path, 'r', encoding='utf-8') as f:
                    self._topics_config = json.load(f)
                logger.info(f"Loaded topics configuration from {topics_path}")
            except Exception as e:
                logger.error(f"Failed to load topics config: {e}")
                raise
        
        return self._topics_config
    
    def get_topics(self) -> List[Dict[str, Any]]:
        """Get list of active topics"""
        config = self._load_topics_config()
        return [topic for topic in config.get("topics", []) if topic.get("active", True)]
    
    def get_score_threshold(self) -> float:
        """Get minimum score threshold for episode inclusion"""
        config = self._load_topics_config()
        return config.get("settings", {}).get("score_threshold", 0.65)
    
    def get_max_words_per_script(self) -> int:
        """Get maximum words per generated script"""
        config = self._load_topics_config()
        return config.get("settings", {}).get("max_words_per_script", 25000)
    
    def get_voice_settings(self, topic_name: str = None) -> Dict[str, Any]:
        """Get voice settings for TTS generation"""
        config = self._load_topics_config()
        
        if topic_name:
            # Get topic-specific voice settings
            for topic in config.get("topics", []):
                if topic.get("name") == topic_name:
                    return {
                        "voice_id": topic.get("voice_id", ""),
                        **config.get("settings", {}).get("default_voice_settings", {})
                    }
        
        # Return default voice settings
        return config.get("settings", {}).get("default_voice_settings", {})
    
    def update_last_modified(self):
        """Update the last_updated timestamp in topics config"""
        config = self._load_topics_config()
        config["last_updated"] = datetime.now().isoformat()
        
        topics_path = self.config_dir / "topics.json"
        try:
            with open(topics_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            
            # Clear cached config to force reload
            self._topics_config = None
            
            logger.info("Updated topics configuration timestamp")
        except Exception as e:
            logger.error(f"Failed to update topics config: {e}")
            raise