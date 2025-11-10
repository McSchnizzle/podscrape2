"""
Configuration Manager for RSS Podcast Transcript Digest System.
Provides centralized access to application configuration.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from src.database.models import get_topic_repo, TopicRepository, Topic

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages application configuration from JSON files"""
    
    def __init__(self, config_dir: str = "config", web_config: Any = None, topic_repo: TopicRepository | None = None):
        # Resolve to project-root-relative config by default to avoid CWD issues
        if config_dir == "config":
            project_root = Path(__file__).parent.parent.parent
            self.config_dir = project_root / config_dir
        else:
            self.config_dir = Path(config_dir)

        # Configuration caching with file modification tracking
        self._topics_config = None
        self._topics_config_mtime = None
        self._topics_config_path = self.config_dir / "topics.json"

        # Optional WebConfigManager injection
        self.web_config = web_config
        # Optional database-backed topic repository
        self.topic_repo = topic_repo
        if self.topic_repo is None:
            try:
                self.topic_repo = get_topic_repo()
                logger.debug("Topic repository initialized from database")
            except Exception as exc:
                logger.debug("Database topic repository unavailable: %s", exc)
                self.topic_repo = None
        
    def _load_topics_config(self) -> Dict[str, Any]:
        """Load topics configuration from JSON file with smart caching"""
        # Check if file exists
        if not self._topics_config_path.exists():
            raise FileNotFoundError(f"Topics config not found: {self._topics_config_path}")

        try:
            # Get current file modification time
            current_mtime = self._topics_config_path.stat().st_mtime

            # Load or reload if cache is empty or file has been modified
            if (self._topics_config is None or
                self._topics_config_mtime != current_mtime):

                with open(self._topics_config_path, 'r', encoding='utf-8') as f:
                    self._topics_config = json.load(f)

                # Check if this was initial load or refresh
                is_initial_load = self._topics_config_mtime is None
                self._topics_config_mtime = current_mtime

                if is_initial_load:
                    logger.info(f"Loaded topics configuration from {self._topics_config_path}")
                else:
                    logger.info(f"Refreshed topics configuration (file modified) from {self._topics_config_path}")
            else:
                logger.debug(f"Using cached topics configuration")

        except Exception as e:
            logger.error(f"Failed to load topics config: {e}")
            raise

        return self._topics_config

    def invalidate_cache(self):
        """Manually invalidate all cached configuration data"""
        self._topics_config = None
        self._topics_config_mtime = None
        logger.info("Configuration cache invalidated")

    def get_topics(self) -> List[Dict[str, Any]]:
        """Get list of active topics."""
        db_topics = self._get_database_topics(active_only=True)
        if db_topics:
            return db_topics

        config = self._load_topics_config()
        return [topic for topic in config.get("topics", []) if topic.get("active", True)]

    def get_all_topics(self) -> List[Dict[str, Any]]:
        """Get list of all topics (including inactive).

        For Web UI management screens where inactive topics must be visible.
        """
        db_topics = self._get_database_topics(active_only=False)
        if db_topics:
            return db_topics

        config = self._load_topics_config()
        return list(config.get("topics", []))
    
    def get_score_threshold(self) -> float:
        """Get minimum score threshold for episode inclusion"""
        if getattr(self, 'web_config', None):
            try:
                return float(self.web_config.get_setting('content_filtering', 'score_threshold', 0.65))
            except Exception:
                pass
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

    def save_topics(self, topics: List[Dict[str, Any]]) -> None:
        """Persist the provided list of topics to topics.json.

        Also updates the last_updated timestamp and clears the in-memory cache.
        """
        config = self._load_topics_config()
        config["topics"] = topics
        config["last_updated"] = datetime.now().isoformat()
        topics_path = self.config_dir / "topics.json"
        try:
            with open(topics_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            # Clear cached config to force reload on next access
            self._topics_config = None
            logger.info("Saved topics configuration with %d topics", len(topics))
        except Exception as e:
            logger.error(f"Failed to save topics config: {e}")
            raise

    def _get_database_topics(self, active_only: bool) -> List[Dict[str, Any]]:
        if not self.topic_repo:
            return []
        try:
            topics = self.topic_repo.get_active_topics() if active_only else self.topic_repo.get_all_topics()
            if not topics:
                return []
            return [self._topic_to_config_dict(topic) for topic in topics if active_only is False or topic.is_active]
        except Exception as exc:
            logger.debug("Falling back to JSON topics due to database error: %s", exc)
            return []

    def _topic_to_config_dict(self, topic: Topic) -> Dict[str, Any]:
        """Convert Topic dataclass to legacy config-style dict for compatibility."""
        return {
            "id": topic.id,
            "slug": topic.slug,
            "name": topic.name,
            "description": topic.description,
            "voice_id": topic.voice_id,
            "voice_settings": topic.voice_settings or {},
            "instructions_md": topic.instructions_md,
            "instruction_file": None,  # retained for legacy compatibility
            "active": topic.is_active,
            "sort_order": topic.sort_order,
            "last_generated_at": topic.last_generated_at.isoformat() if topic.last_generated_at else None,
            "source": "database",
            # Multi-voice dialogue support (v1.79+)
            "use_dialogue_api": topic.use_dialogue_api,
            "dialogue_model": topic.dialogue_model,
            "voice_config": topic.voice_config
        }
