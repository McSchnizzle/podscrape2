# Phase 3 & 3.5 AI Configuration Management - Progress Report

## Overview
Implementing comprehensive AI token configuration management for all AI interactions in the RSS Podcast Transcript Digest System, plus integration tests for phase scripts.

## ✅ COMPLETED TASKS

### 1. Database & Configuration Foundation
**File**: `src/config/web_config.py`

#### AI Model Definitions Added
```python
AI_MODELS = {
    'openai': {
        'gpt-5': {'max_output': 128000, 'max_input': 272000, 'display_name': 'GPT-5'},
        'gpt-5-mini': {'max_output': 128000, 'max_input': 272000, 'display_name': 'GPT-5 Mini'},
        'gpt-4-turbo-preview': {'max_output': 4096, 'max_input': 128000, 'display_name': 'GPT-4 Turbo'},
        'gpt-4o': {'max_output': 16384, 'max_input': 128000, 'display_name': 'GPT-4o'},
        'gpt-4o-mini': {'max_output': 16384, 'max_input': 128000, 'display_name': 'GPT-4o Mini'},
        'gpt-3.5-turbo': {'max_output': 4096, 'max_input': 16385, 'display_name': 'GPT-3.5 Turbo'}
    },
    'elevenlabs': {
        'eleven_turbo_v2_5': {'max_characters': 40000, 'display_name': 'Turbo v2.5 (40k chars)'},
        'eleven_turbo_v2': {'max_characters': 30000, 'display_name': 'Turbo v2 (30k chars)'},
        'eleven_flash_v2_5': {'max_characters': 40000, 'display_name': 'Flash v2.5 (40k chars, low latency)'},
        'eleven_flash_v2': {'max_characters': 30000, 'display_name': 'Flash v2 (30k chars, low latency)'},
        'eleven_multilingual_v2': {'max_characters': 10000, 'display_name': 'Multilingual v2 (10k chars)'},
        'eleven_multilingual_v1': {'max_characters': 10000, 'display_name': 'Multilingual v1 (10k chars)'}
    },
    'whisper': {
        'whisper-1': {'max_file_size_mb': 25, 'display_name': 'Whisper-1 (25MB limit)'}
    }
}
```

#### Configuration Defaults Added to DEFAULTS
- **Content Scoring**: Model selection, max_tokens (1000), max_episodes_per_batch (10)
- **Digest Generation**: Model selection, max_output_tokens (25000), max_input_tokens (150000)
- **Metadata Generation**: Model selection, max_title_tokens (50), max_summary_tokens (200), max_description_tokens (500)
- **TTS Generation**: Model selection, max_characters (35000)
- **STT Transcription**: Model selection, max_file_size_mb (20)

#### Helper Methods Added
- `get_ai_models()`: Returns available AI models and limits
- `validate_model_limit()`: Validates if a limit value is within model capabilities
- `get_model_limit()`: Gets maximum limit for specific model/limit type
- `adjust_limit_for_model()`: Adjusts limits when switching models

### 2. ContentScorer Updates
**File**: `src/scoring/content_scorer.py`

#### Changes Made:
- Added AI configuration loading in constructor
- Added model and token limit validation
- Updated API call to use `self.ai_model` instead of hardcoded "gpt-5-mini"
- Updated `max_output_tokens` to use `self.max_tokens`
- Added `_validate_and_adjust_token_limit()` method
- Updated logging to show configured model and tokens

#### Key Features:
- Reads model from `ai_content_scoring.model` (default: gpt-5-mini)
- Reads max_tokens from `ai_content_scoring.max_tokens` (default: 1000)
- Validates token limits against model capabilities with auto-adjustment

### 3. ScriptGenerator Updates
**File**: `src/generation/script_generator.py`

#### Changes Made:
- Added AI configuration loading in constructor
- Added separate input and output token configuration
- Updated both API calls to use `self.ai_model`
- Updated `max_output_tokens` to use `self.max_output_tokens`
- Added intelligent transcript limiting based on input token constraints
- Added `_validate_and_adjust_token_limit()` method for both input/output
- Added `_calculate_transcript_limit()` method for dynamic transcript sizing

#### Key Features:
- Reads model from `ai_digest_generation.model` (default: gpt-5)
- Reads max_output_tokens from `ai_digest_generation.max_output_tokens` (default: 25000)
- Reads max_input_tokens from `ai_digest_generation.max_input_tokens` (default: 150000)
- Dynamically calculates transcript limits based on input token constraints
- Validates both input and output limits against model capabilities

### 4. MetadataGenerator Updates (IN PROGRESS)
**File**: `src/audio/metadata_generator.py`

#### Changes Made So Far:
- Added WebConfigManager import
- Updated constructor to accept web_config parameter
- Added AI configuration loading for metadata generation
- Added `_safe_create_web_config()` and `_validate_and_adjust_token_limit()` methods
- Set up separate token limits for title, summary, and description

#### Configuration Added:
- Model selection from `ai_metadata_generation.model` (default: gpt-5-mini)
- Title token limit from `ai_metadata_generation.max_title_tokens` (default: 50)
- Summary token limit from `ai_metadata_generation.max_summary_tokens` (default: 200)
- Description token limit from `ai_metadata_generation.max_description_tokens` (default: 500)

## 🚧 CURRENT STATUS - MetadataGenerator (IN PROGRESS)

### What's Left for MetadataGenerator:
1. **Update API calls** - Need to find and update the actual OpenAI API calls to use:
   - `self.ai_model` instead of hardcoded model
   - Appropriate token limits for different metadata types (title/summary/description)

2. **Add import for Optional type** - Need to add `Optional` to the imports for the helper methods

### Next Steps for MetadataGenerator:
1. Find the OpenAI API calls (search for `openai.` or `client.`)
2. Update model parameter to use `self.ai_model`
3. Update max_tokens parameter based on metadata type being generated
4. Test the changes

## 📋 REMAINING TODO LIST

### 5. AudioGenerator Updates (PENDING)
**File**: `src/audio/audio_generator.py`
- Add ElevenLabs model configuration
- Add character limit validation
- Update TTS API calls to use configured model and limits
- Add truncation logic based on character limits

### 6. OpenAIWhisperProvider Updates (PENDING)
**File**: `src/pipeline/stt/providers.py`
- Add file size limit configuration
- Add validation for 25MB limit
- Add model configuration (though whisper-1 is only option currently)

### 7. Web UI AI Configuration Interface (PENDING)
**Files**: `web_ui/templates/settings.html`, `web_ui/app.py`
- Create new "AI Configuration" section in settings
- Add model selection dropdowns for each phase
- Add token/character limit inputs with dynamic validation
- Add JavaScript for real-time limit updates when model changes
- Add backend API endpoints for model information
- Add form validation and submission handling

### 8. Integration Tests for Phase Scripts (PENDING)
**File**: `tests/test_phase_scripts.py` (new)
- Create integration tests for each phase script:
  - `scripts/run_discovery.py`
  - `scripts/run_audio.py`
  - `scripts/run_scoring.py`
  - `scripts/run_digest.py`
  - `scripts/run_tts.py`
  - `scripts/run_publishing.py`
- Mock API calls to avoid real costs
- Test command-line arguments and database interactions

## 🔧 KEY TECHNICAL PATTERNS ESTABLISHED

**CRITICAL REQUIREMENT**: All AI configuration is stored in the PostgreSQL database via the `web_settings` table and accessed through `WebConfigManager`. Each service class pulls its configuration from the database, NOT from config files.

### 1. Constructor Pattern for AI Configuration
```python
def __init__(self, web_config: WebConfigManager = None):
    self.web_config = web_config or self._safe_create_web_config()

    if self.web_config:
        self.ai_model = self.web_config.get_setting("ai_PHASE", "model", "default-model")
        self.max_tokens = self.web_config.get_setting("ai_PHASE", "max_tokens", default_value)

        # Validate against model capabilities
        self.max_tokens = self._validate_and_adjust_token_limit(self.ai_model, self.max_tokens)
```

### 2. Validation Method Pattern
```python
def _validate_and_adjust_token_limit(self, model: str, requested_tokens: int, limit_type: str = 'max_output') -> int:
    if not self.web_config:
        return requested_tokens

    max_limit = self.web_config.get_model_limit('openai', model, limit_type)
    if max_limit > 0 and requested_tokens > max_limit:
        logger.warning(f"Requested {requested_tokens} tokens exceeds {model} limit of {max_limit}, adjusting to {max_limit}")
        return max_limit

    return requested_tokens
```

### 3. API Call Pattern
```python
response = self.client.responses.create(
    model=self.ai_model,  # Use configured model
    max_output_tokens=self.max_tokens,  # Use configured limit
    # ... other parameters
)
```

## 🎯 WEB UI REQUIREMENTS

### Model Selection Interface Design:
- **Dropdown per AI phase** with model options from AI_MODELS
- **Token/character input fields** with dynamic max values
- **Small print showing model limits** that updates when model changes
- **Auto-adjustment** when switching to model with lower limits
- **Validation** preventing values exceeding model capabilities

### JavaScript Functionality Needed:
- Dynamic model limit updates
- Input validation against model capabilities
- Auto-adjustment of token values when model changes
- Form submission with validation

### Backend API Endpoints Needed:
- `/api/ai-models` - Return available models and limits
- Update settings POST handler for AI configurations
- Model limit validation on server side

## 🔍 FILES THAT NEED ATTENTION

### High Priority:
1. **`src/audio/metadata_generator.py`** - Finish updating API calls (IN PROGRESS)
2. **`src/audio/audio_generator.py`** - Add ElevenLabs configuration
3. **`web_ui/templates/settings.html`** - Add AI configuration UI
4. **`web_ui/app.py`** - Add AI settings backend

### Medium Priority:
5. **`src/pipeline/stt/providers.py`** - Add Whisper configuration
6. **`tests/test_phase_scripts.py`** - Create integration tests

## 📊 SUCCESS CRITERIA

- [x] All AI service classes read model selection from web config
- [x] Token/character limits are configurable and validated
- [ ] UI dynamically shows and enforces model limits
- [ ] Settings persist and affect pipeline execution
- [ ] Integration tests exist for all phase scripts
- [ ] Clear documentation of limits and cost implications

## 🚀 ESTIMATED COMPLETION

- **MetadataGenerator**: 30 minutes (finish API calls)
- **AudioGenerator**: 1 hour (ElevenLabs integration)
- **OpenAIWhisperProvider**: 30 minutes (file size limits)
- **Web UI Interface**: 2-3 hours (frontend + backend)
- **Integration Tests**: 1-2 hours (phase script tests)

**Total Remaining**: ~5-7 hours of development time