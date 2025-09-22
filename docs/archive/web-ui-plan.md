# Local Web UI Management Plan for RSS Podcast Digest System

## Overview

This plan outlines the development of a local web interface to manage all configurable settings in the RSS Podcast Digest System. The interface will allow real-time configuration changes without code modifications, providing full control over the podcast processing pipeline.

## Current Configuration State Analysis

### Existing Configuration Files
1. **`config/topics.json`** - Topics, voice settings, score thresholds
2. **`config/channels.json`** - YouTube channels (currently unused but ready)
3. **Database** - RSS feeds, episodes, digests stored in SQLite

### Embedded Settings Throughout Codebase
1. **Audio Processing**: 10-minute chunks (`parakeet_transcriber.py:10`)
2. **Episode Lookback**: 7-day default (`rss_models.py`, `complete_audio_processor.py`)
3. **Publishing Pipeline**: 30-day lookback (`run_publishing_pipeline.py`)
4. **Retention Policies**: 7-14 day cleanup cycles
5. **Max Episodes**: 5 episodes per digest (`script_generator.py:max_episodes=5`)
6. **Score Threshold**: 0.65 default (`config_manager.py`)
7. **Script Length**: 25,000 words max (`config_manager.py`)
8. **Voice Settings**: Stability, similarity, style values
9. **Test Mode**: 2-chunk testing vs full transcription

## Web UI Architecture

### Technology Stack
- **Backend**: Flask (Python web framework)
- **Frontend**: HTML5 + TailwindCSS + Alpine.js (lightweight, no build process)
- **Database**: Existing SQLite database + new `web_settings` table
- **Development Server**: Built-in Flask development server (localhost only)

### Project Structure
```
web_ui/
├── app.py                 # Flask application entry point
├── routes/
│   ├── __init__.py
│   ├── dashboard.py       # Main dashboard
│   ├── topics.py          # Topic management
│   ├── feeds.py           # RSS feed management
│   ├── processing.py      # Processing settings
│   └── system.py          # System-wide settings
├── models/
│   ├── __init__.py
│   ├── settings.py        # Settings database model
│   └── web_config.py      # Web UI configuration
├── templates/
│   ├── base.html          # Base template with TailwindCSS
│   ├── dashboard.html     # Main dashboard
│   ├── topics.html        # Topic management page
│   ├── feeds.html         # Feed management page
│   ├── processing.html    # Processing settings page
│   └── system.html        # System settings page
├── static/
│   ├── css/
│   │   └── app.css        # Custom styles
│   └── js/
│       └── app.js         # Alpine.js components
└── requirements.txt       # Python dependencies
```

## Database Schema Changes

### New `web_settings` Table
```sql
CREATE TABLE web_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    setting_key TEXT NOT NULL,
    setting_value TEXT NOT NULL,
    value_type TEXT NOT NULL DEFAULT 'string', -- string, integer, float, boolean, json
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category, setting_key)
);
```

### Settings Categories
1. **audio_processing**: Chunk sizes, duration limits, quality settings
2. **content_filtering**: Score thresholds, episode limits, lookback periods  
3. **voice_generation**: TTS settings, voice configurations
4. **publishing**: Deployment settings, retention policies
5. **system**: Test modes, debug flags, performance settings

## Configuration Management System

### New Configuration Classes

#### `WebConfigManager` Class
```python
class WebConfigManager:
    """Manages all web UI configurable settings"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self._cache = {}
    
    def get_setting(self, category: str, key: str, default=None):
        """Get setting value with type conversion"""
    
    def set_setting(self, category: str, key: str, value, value_type: str):
        """Set setting with validation and type conversion"""
    
    def get_category_settings(self, category: str) -> Dict:
        """Get all settings for a category"""
    
    def validate_setting(self, category: str, key: str, value) -> bool:
        """Validate setting value and constraints"""
```

#### Setting Definitions with Validation
```python
SETTING_DEFINITIONS = {
    'audio_processing': {
        'chunk_duration_minutes': {
            'type': 'integer',
            'default': 10,
            'min': 1, 'max': 30,
            'description': 'Audio chunk duration for transcription processing'
        },
        'max_processing_chunks': {
            'type': 'integer', 
            'default': None,  # None = process all
            'min': 1, 'max': 50,
            'description': 'Max chunks to process (testing mode)'
        }
    },
    'content_filtering': {
        'score_threshold': {
            'type': 'float',
            'default': 0.65,
            'min': 0.0, 'max': 1.0,
            'description': 'Minimum relevance score for episode inclusion'
        },
        'max_episodes_per_digest': {
            'type': 'integer',
            'default': 5,
            'min': 1, 'max': 20,
            'description': 'Maximum episodes per topic digest'
        },
        'episode_lookback_days': {
            'type': 'integer', 
            'default': 7,
            'min': 1, 'max': 30,
            'description': 'Days to look back for new episodes'
        }
    },
    'publishing': {
        'publishing_lookback_days': {
            'type': 'integer',
            'default': 30, 
            'min': 1, 'max': 90,
            'description': 'Days to search for unpublished digests'
        },
        'cleanup_retention_days': {
            'type': 'integer',
            'default': 7,
            'min': 1, 'max': 30,
            'description': 'Days to retain local audio files'
        }
    }
}
```

## Code Modifications Required

### 1. Core Configuration Integration

#### Modify `src/config/config_manager.py`
```python
class ConfigManager:
    def __init__(self, config_dir: str = "config", web_config: WebConfigManager = None):
        self.web_config = web_config
        # ... existing code ...
    
    def get_score_threshold(self) -> float:
        if self.web_config:
            return self.web_config.get_setting('content_filtering', 'score_threshold', 0.65)
        # Fallback to existing JSON config
        config = self._load_topics_config()
        return config.get("settings", {}).get("score_threshold", 0.65)
```

#### Modify `src/podcast/parakeet_transcriber.py`
```python
class ParakeetTranscriber:
    def __init__(self, model_name: str = "nvidia/parakeet-rnnt-0.6b", 
                 device: str = "auto", 
                 chunk_duration_minutes: int = None,
                 web_config: WebConfigManager = None):
        
        if chunk_duration_minutes is None:
            if web_config:
                chunk_duration_minutes = web_config.get_setting(
                    'audio_processing', 'chunk_duration_minutes', 10)
            else:
                chunk_duration_minutes = 10
        
        self.chunk_duration_seconds = chunk_duration_minutes * 60
        # ... rest of initialization
```

### 2. Factory Pattern for Dependency Injection

#### New `src/web_ui/factories.py`
```python
class ServiceFactory:
    """Factory for creating services with web configuration"""
    
    def __init__(self, db_manager, web_config):
        self.db_manager = db_manager
        self.web_config = web_config
    
    def create_transcriber(self):
        return ParakeetTranscriber(
            chunk_duration_minutes=self.web_config.get_setting(
                'audio_processing', 'chunk_duration_minutes', 10),
            web_config=self.web_config
        )
    
    def create_config_manager(self):
        return ConfigManager(web_config=self.web_config)
```

### 3. Settings Migration and Initialization

#### Database Migration Script
```python
def migrate_existing_settings_to_web_config():
    """Migrate settings from JSON files to web_settings table"""
    
    # Migrate from config/topics.json
    with open('config/topics.json') as f:
        topics_config = json.load(f)
    
    settings_to_migrate = {
        ('content_filtering', 'score_threshold'): topics_config.get('settings', {}).get('score_threshold', 0.65),
        ('content_filtering', 'max_words_per_script'): topics_config.get('settings', {}).get('max_words_per_script', 25000),
        # ... other migrations
    }
    
    for (category, key), value in settings_to_migrate.items():
        web_config.set_setting(category, key, value, type(value).__name__)
```

## Web UI Features and Pages

### 1. Dashboard (`/`)
- **System Status**: Current processing pipeline status
- **Recent Activity**: Last processed episodes, generated digests
- **Quick Settings**: Most commonly changed settings
- **Resource Usage**: Audio file count, database size, cache status

### 2. Topics Management (`/topics`)
- **Topic List**: All configured topics with active/inactive status
- **Add/Edit Topics**: Name, description, instruction file, voice ID
- **Voice Settings**: Per-topic TTS configuration
- **Topic-Specific Settings**: Score thresholds, episode limits

### 3. RSS Feeds Management (`/feeds`)
- **Active Feeds**: Currently monitored RSS feeds
- **Add New Feeds**: URL validation, feed metadata detection
- **Feed Health**: Last check time, consecutive failures, episode counts
- **Bulk Operations**: Enable/disable multiple feeds

### 4. Processing Settings (`/processing`)
- **Audio Processing**: Chunk duration, max processing time
- **Content Filtering**: Score thresholds, episode limits, lookback periods
- **Testing Mode**: Enable/disable test mode with chunk limits
- **Performance**: Concurrent processing, memory limits

### 5. System Settings (`/system`)
- **Publishing**: Vercel deployment, GitHub integration
- **Retention**: File cleanup policies, database maintenance
- **Logging**: Log levels, debugging options
- **API Keys**: Manage external service credentials (masked)

## Real-time Configuration Updates

### Configuration Change Workflow
1. **User submits form** → Validation on client and server
2. **Server updates database** → `web_settings` table updated
3. **Cache invalidation** → Clear relevant configuration cache
4. **Notification system** → Show success/error messages
5. **Live preview** → Show effects of changes where possible

### Change Tracking
- **Audit Log**: Track all configuration changes with timestamps
- **Rollback Capability**: Ability to revert to previous settings
- **Export/Import**: Backup and restore configurations

## Settings Validation and Constraints

### Client-Side Validation (Alpine.js)
```javascript
function validateSetting(category, key, value) {
    const definition = settingDefinitions[category][key];
    
    if (definition.type === 'integer') {
        const num = parseInt(value);
        return num >= definition.min && num <= definition.max;
    }
    
    if (definition.type === 'float') {
        const num = parseFloat(value);
        return num >= definition.min && num <= definition.max;
    }
    
    return true;
}
```

### Server-Side Validation
```python
def validate_setting_change(category: str, key: str, value, setting_def: dict) -> Tuple[bool, str]:
    """Validate setting change against definition"""
    
    if setting_def['type'] == 'integer':
        try:
            val = int(value)
            if val < setting_def['min'] or val > setting_def['max']:
                return False, f"Value must be between {setting_def['min']} and {setting_def['max']}"
        except ValueError:
            return False, "Must be a valid integer"
    
    return True, ""
```

## Implementation Phases

### Phase 1: Foundation (Week 1)
- Set up Flask application structure
- Create database migrations for `web_settings` table
- Implement basic `WebConfigManager` class
- Create base templates with TailwindCSS

### Phase 2: Core Functionality (Week 2)
- Implement dashboard with system status
- Add topics management page
- Create RSS feeds management interface
- Implement settings validation system

### Phase 3: Advanced Features (Week 3)
- Add processing settings page
- Implement real-time configuration updates
- Create settings import/export functionality
- Add change tracking and audit logs

### Phase 4: Integration (Week 4)
- Modify core system components to use web configuration
- Implement factory pattern for dependency injection
- Add comprehensive testing
- Documentation and deployment guide

## Security Considerations

### Local Development Only
- Flask debug mode enabled by default
- Bind to localhost (127.0.0.1) only
- No authentication required (local development)
- File system access restricted to project directory

### Input Validation
- Server-side validation for all settings
- SQL injection protection via parameterized queries
- File path validation for instruction files
- Rate limiting on configuration changes

### Data Protection
- API keys displayed masked in UI
- Configuration backups exclude sensitive data
- Database backup before major changes

## Testing Strategy

### Unit Tests
- `WebConfigManager` functionality
- Settings validation logic
- Database operations
- Configuration migration

### Integration Tests  
- Web UI form submissions
- Configuration propagation to core system
- Real-time updates functionality
- Import/export operations

### User Acceptance Tests
- Complete workflow testing
- Error handling scenarios
- Performance under load
- Cross-browser compatibility

## Deployment and Usage

### Local Development Setup
```bash
cd web_ui/
pip install -r requirements.txt
python app.py
# Navigate to http://localhost:5000
```

### Configuration Backup Strategy
- Automatic backup before changes
- Manual export functionality  
- Version control integration for configs
- Rollback capabilities

### Monitoring and Logging
- Configuration change logging
- Error tracking and alerting
- Performance monitoring
- Usage analytics

## Future Enhancements

### Advanced Features
- **Real-time Pipeline Monitoring**: Live status updates during processing
- **A/B Testing Framework**: Test different configurations simultaneously
- **Automated Optimization**: ML-based setting recommendations
- **Multi-Environment Support**: Development vs. production configurations

### API Development
- REST API for programmatic access
- Webhook notifications for configuration changes
- Integration with external monitoring systems
- CLI interface for automation

### Advanced UI Features
- **Dark Mode**: Toggle between light and dark themes
- **Responsive Design**: Mobile-friendly interface
- **Keyboard Shortcuts**: Power user efficiency
- **Search and Filtering**: Find settings quickly

This comprehensive plan provides a roadmap for creating a local web interface that gives full control over the RSS Podcast Digest System configuration without requiring code changes for routine adjustments.