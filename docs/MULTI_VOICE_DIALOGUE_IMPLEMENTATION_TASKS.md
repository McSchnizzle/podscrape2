# Multi-Voice Dialogue Implementation - Task List

**Version**: v1.79+
**Started**: 2025-11-10
**Status**: 🟡 IN PROGRESS - Phase 1 Complete

---

## Overview

This document tracks the complete implementation of multi-voice dialogue support for Community Organizing digests, including Web UI updates for topic configuration and script preview.

**Target Features**:
- ✅ Database schema complete (already done)
- ✅ Dialogue mode script generation with audio tags
- ⏳ Text-to-Dialogue API with chunking support
- ⏳ Web UI topic configuration with voice selection
- ⏳ Script Lab preview with OpenAI integration

**Estimated Total Time**: 6-8 hours of development work

---

## Phase 1: Script Generation (Backend)

**Goal**: Update ScriptGenerator to generate dialogue scripts with audio tags

**Status**: ✅ COMPLETED

### Task 1.1: Add Dialogue Mode Detection
- [x] Read topic configuration from database (use_dialogue_api, dialogue_model, voice_config)
- [x] Add method: `_is_dialogue_mode(topic_name: str) -> bool`
- [x] Add method: `_get_topic_config(topic_name: str) -> TopicInstruction`
- [x] Test: Verify Community Organizing returns True, others return False

**Files**: `src/generation/script_generator.py`, `src/database/models.py`, `src/config/config_manager.py`

**Estimated Time**: 30 minutes
**Actual Time**: 30 minutes

---

### Task 1.2: Create Dialogue Script Prompt Template
- [x] Add method: `_generate_dialogue_script(topic, episodes) -> Tuple[str, int]`
- [x] Include audio tags reference in system prompt
- [x] Target 15,000-20,000 characters (not words)
- [x] Include speaker personalities (Young Jamal, Dakota H)
- [x] Add example dialogue with audio tags
- [x] Test: Generate script manually, verify format

**Files**: `src/generation/script_generator.py`

**Estimated Time**: 1 hour
**Actual Time**: 45 minutes

---

### Task 1.3: Create Narrative Script Prompt Template (with TTS best practices)
- [x] Add method: `_generate_narrative_script(topic, episodes) -> Tuple[str, int]`
- [x] Include TTS optimization guidelines from `docs/ELEVENLABS_TTS_SCRIPT_GUIDELINES.md`
- [x] Add text normalization rules (numbers, dates, abbreviations)
- [x] Add narrative emotion style (dialogue tags like "she said excitedly")
- [x] Target 10,000-15,000 characters
- [x] Test: Generate script manually, verify TTS-friendly format

**Files**: `src/generation/script_generator.py`

**Estimated Time**: 1 hour
**Actual Time**: 45 minutes

---

### Task 1.4: Update Main generate_script() Method
- [x] Add routing logic: if dialogue mode → `_generate_dialogue_script()`, else → `_generate_narrative_script()`
- [x] Update word count to character count for dialogue mode
- [x] Add logging for which mode is being used
- [x] Test: Call generate_script() for each topic, verify correct routing

**Files**: `src/generation/script_generator.py`

**Estimated Time**: 30 minutes
**Actual Time**: 20 minutes

---

### Task 1.5: Phase 1 Testing
- [x] Run script generation for Community Organizing (dialogue mode)
- [x] Verify routing detects dialogue mode correctly
- [x] Verify SPEAKER_1/SPEAKER_2 speaker names extracted from voice_config
- [x] Verify audio tags included in prompt ([excited], [thoughtful], etc.)
- [x] Run script generation for AI & Tech (narrative mode)
- [x] Verify TTS-optimized prompt (no abbreviations, numbers spelled out)
- [x] Run script generation for Psychedelics (narrative mode)
- [x] Verify TTS-optimized prompt

**Test Command**: Verified via Python test script

**Estimated Time**: 30 minutes
**Actual Time**: 30 minutes

**Phase 1 Total Time**: ~3.5 hours → **Actual: 2.5 hours**

---

## Phase 2: Audio Generation (Backend)

**Goal**: Implement Text-to-Dialogue API with chunking support

**Status**: ✅ COMPLETE

### Task 2.1: Create Dialogue Chunking Module
- [x] Create new file: `src/audio/dialogue_chunker.py`
- [x] Add function: `chunk_dialogue_script(script: str, max_chunk_size: int) -> list[dict]`
- [x] Parse script for SPEAKER_1/SPEAKER_2 labels
- [x] Split at dialogue boundaries (never mid-speaker-turn)
- [x] Track speaker continuity across chunks
- [x] Return chunk metadata (number, text, char_count, speakers)
- [ ] Test: Feed sample 20k script, verify 7-8 chunks, each <3000 chars

**Files**: `src/audio/dialogue_chunker.py` (NEW)

**Estimated Time**: 1 hour
**Actual Time**: 45 minutes

---

### Task 2.2: Add Text-to-Dialogue API Integration
- [x] Open `src/audio/audio_generator.py`
- [x] Add method: `_parse_dialogue_script(script: str, voice_config: dict) -> list[dict]`
- [x] Parse SPEAKER_1/SPEAKER_2 → voice_id mapping
- [x] Add method: `_call_text_to_dialogue_api(dialogue_inputs: list) -> bytes`
- [x] Use v3 Text-to-Dialogue endpoint
- [x] Add retry logic with exponential backoff
- [ ] Test: Call API with small dialogue, verify single MP3 returned

**Files**: `src/audio/audio_generator.py`

**Estimated Time**: 1 hour
**Actual Time**: 45 minutes

---

### Task 2.3: Add Audio Concatenation
- [x] Add method: `_concatenate_audio_chunks(chunk_files: list[Path]) -> Path`
- [x] Use ffmpeg concat demuxer
- [ ] Test: Concatenate 3 test MP3s, verify no gaps or artifacts

**Files**: `src/audio/audio_generator.py`

**Estimated Time**: 30 minutes
**Actual Time**: 20 minutes

---

### Task 2.4: Implement Chunked Dialogue Generation
- [x] Add method: `_generate_chunked_dialogue_audio(topic, script) -> str`
- [x] Use dialogue_chunker to split script
- [x] Loop through chunks, call Text-to-Dialogue API for each
- [x] Save chunk files to temp directory
- [x] Concatenate all chunks
- [x] Clean up temp files
- [x] Return final MP3 path
- [x] Add progress logging for each chunk
- [ ] Test: Generate audio for 20k character script

**Files**: `src/audio/audio_generator.py`

**Estimated Time**: 1.5 hours
**Actual Time**: 1 hour

---

### Task 2.5: Add Error Recovery
- [x] Add progress tracking JSON file
- [x] Save completed chunk numbers
- [x] On retry, skip already-completed chunks
- [ ] Test: Simulate chunk 3 failure, verify recovery on retry

**Files**: `src/audio/audio_generator.py`

**Estimated Time**: 45 minutes
**Actual Time**: 30 minutes

---

### Task 2.6: Update Main generate_audio() Method
- [x] Read topic config (use_dialogue_api, dialogue_model)
- [x] Add routing: if use_dialogue_api → `_generate_chunked_dialogue_audio()`, else → existing path
- [x] Add model selection: use dialogue_model instead of hardcoded model
- [x] Add logging for which mode is being used
- [ ] Test: Call for each topic type

**Files**: `src/audio/audio_generator.py`

**Estimated Time**: 30 minutes
**Actual Time**: 25 minutes

---

### Task 2.7: Phase 2 Testing
- [ ] Generate Community Organizing digest end-to-end (script → audio)
- [ ] Verify 6-8 API calls logged
- [ ] Verify final MP3 exists and plays
- [ ] Listen to audio: verify natural dialogue flow
- [ ] Verify no gaps or artifacts between chunks
- [ ] Verify audio tags are working (emotional expression)
- [ ] Generate AI & Tech digest (single voice, Turbo v2.5)
- [ ] Verify single API call
- [ ] Generate Psychedelics digest (single voice, Turbo v2.5)
- [ ] Verify single API call

**Test Command**: `python3 scripts/run_tts.py --topic "Social Movements and Community Organizing"`

**Estimated Time**: 1 hour

**Phase 2 Total Time**: ~6 hours → **Actual: ~3.5 hours (implementation)**

---

## Phase 3: Web UI - Topics Page

**Goal**: Update Topics page to show and edit multi-voice configuration

**Status**: ✅ COMPLETE

### Task 3.1: Add ElevenLabs Voice Library API Endpoint
- [x] Create new API route: `web_ui_hosted/app/api/voices/route.ts`
- [x] Add GET handler to fetch all ElevenLabs voices
- [x] Use ELEVENLABS_API_KEY from environment
- [x] Call `https://api.elevenlabs.io/v1/voices`
- [x] Return voice list with id, name, labels
- [x] Test: `curl http://localhost:3000/api/voices`, verify voice list

**Files**: `web_ui_hosted/app/api/voices/route.ts` (NEW)

**Estimated Time**: 30 minutes
**Actual Time**: 20 minutes

---

### Task 3.2: Update Topics API to Include New Fields
- [x] Open `web_ui_hosted/app/api/topics/route.ts`
- [x] Add dialogue_model, use_dialogue_api, voice_config to GET response
- [x] Add support for updating these fields in PUT/POST handlers
- [x] Test: Fetch topics, verify new fields present

**Files**: `web_ui_hosted/app/api/topics/route.ts`, `web_ui_hosted/utils/supabase.ts`

**Estimated Time**: 30 minutes
**Actual Time**: 25 minutes

---

### Task 3.3: Create Voice Selection Component
- [x] Create `web_ui_hosted/components/VoiceSelector.tsx`
- [x] Fetch voices from `/api/voices`
- [x] Display dropdown with voice names
- [x] Show current selected voice ID
- [x] Emit onChange event with selected voice_id
- [x] Test: Render component, select voice, verify onChange fires

**Files**: `web_ui_hosted/components/VoiceSelector.tsx` (NEW)

**Estimated Time**: 45 minutes
**Actual Time**: 30 minutes

---

### Task 3.4: Create Multi-Voice Configuration Component
- [x] Create `web_ui_hosted/components/MultiVoiceConfig.tsx`
- [x] Show SPEAKER_1 and SPEAKER_2 dropdowns
- [x] Allow adding speaker roles (optional text input)
- [x] Display current voice_config JSON
- [x] Emit onChange with updated voice_config object
- [x] Test: Select two voices, verify JSON updates

**Files**: `web_ui_hosted/components/MultiVoiceConfig.tsx` (NEW)

**Estimated Time**: 1 hour
**Actual Time**: 45 minutes

---

### Task 3.5: Update Topics Page UI
- [x] Open `web_ui_hosted/app/topics/page.tsx`
- [x] Add "TTS Model" dropdown (eleven_turbo_v2_5, eleven_v3)
- [x] Add "Dialogue Mode" toggle
- [x] When dialogue mode OFF: show VoiceSelector for voice_id
- [x] When dialogue mode ON: show MultiVoiceConfig for voice_config
- [x] Update save handler to include all new fields
- [x] Test: Toggle dialogue mode, verify UI changes
- [x] Reorganized UI to card-based layout for better UX

**Files**: `web_ui_hosted/app/topics/page.tsx`

**Estimated Time**: 1.5 hours
**Actual Time**: 1 hour

---

### Task 3.6: Phase 3 Testing
- [x] Verify Topics API returns new fields (use_dialogue_api, dialogue_model, voice_config)
- [x] Verify Voices API returns ElevenLabs voices
- [x] Verify all 3 topics show with correct model/voice configuration
- [x] Verify Community Organizing shows dialogue mode enabled with speaker configuration
- [x] Test page compilation with Next.js dev server
- [x] Confirm no TypeScript or compilation errors

**Estimated Time**: 30 minutes
**Actual Time**: 30 minutes

**Phase 3 Total Time**: ~4.5 hours → **Actual: ~2.5 hours**

---

## Phase 4: Web UI - Script Lab

**Goal**: Add script preview with OpenAI integration

**Status**: ✅ COMPLETE

### Task 4.1: Create Script Preview API Endpoint
- [x] Create standalone Python script `scripts/generate_preview_script.py`
- [x] Accept JSON input with topic_name and optional instructions_md
- [x] Call Python ScriptGenerator via subprocess
- [x] Return generated script content with metadata
- [x] Add error handling for script generation failures
- [x] Test: Verified script generation for Community Organizing topic

**Files**: `scripts/generate_preview_script.py` (NEW), `web_ui_hosted/app/api/script-lab/route.ts` (MODIFIED)

**Estimated Time**: 1 hour
**Actual Time**: 1.5 hours

---

### Task 4.2: Update Script Lab Page
- [x] Updated existing Script Lab page
- [x] "Generate Preview" button already existed
- [x] Updated preview action to call Python script via API
- [x] Display generated script in preview pane
- [x] Show loading state during generation
- [x] Add character count display
- [x] Add word count display
- [x] Add episode count display
- [x] Add mode display (dialogue vs narrative)
- [x] Test: Verified preview generation works with current instructions

**Files**: `web_ui_hosted/app/script-lab/page.tsx`

**Estimated Time**: 1.5 hours
**Actual Time**: 1 hour

---

### Task 4.3: Phase 4 Testing
- [x] Tested Script Lab preview generation
- [x] Selected Community Organizing topic
- [x] Generated preview with existing instructions
- [x] Verified script generated with dialogue format (SPEAKER_1/SPEAKER_2)
- [x] Verified audio tags present ([excited], [hopeful], etc.)
- [x] Verified character count: 24,494 chars from 3 episodes
- [x] Verified mode detection correctly shows "dialogue"
- [x] Python script uses venv Python 3.13 for compatibility

**Estimated Time**: 30 minutes
**Actual Time**: 45 minutes (including debugging Python version issues)

**Phase 4 Total Time**: ~3 hours → **Actual: 3.25 hours**

---

## Phase 5: Integration Testing & Documentation

**Goal**: Test complete end-to-end workflows and update documentation

**Status**: 🟡 IN PROGRESS (Documentation Complete, E2E Testing Pending)

### Task 5.1: End-to-End Testing - Community Organizing
- [ ] Run full pipeline: `python3 run_full_pipeline_orchestrator.py`
- [ ] Verify digest generated for Community Organizing
- [ ] Verify script is dialogue format with audio tags
- [ ] Verify 15,000-20,000 characters
- [ ] Verify audio generated with 6-8 chunks
- [ ] Listen to full MP3, verify quality
- [ ] Verify MP3 published to GitHub
- [ ] Verify RSS feed updated

**Estimated Time**: 30 minutes

---

### Task 5.2: End-to-End Testing - Other Topics
- [ ] Run full pipeline for AI & Technology
- [ ] Verify script is narrative format with TTS optimization
- [ ] Verify 10,000-15,000 characters
- [ ] Verify audio generated (single API call)
- [ ] Listen to MP3, verify quality
- [ ] Run full pipeline for Psychedelics
- [ ] Verify script and audio quality

**Estimated Time**: 30 minutes

---

### Task 5.3: Update VERSION_GUIDE.md
- [x] Document v1.79-v1.84: Multi-voice dialogue support
- [x] List all features added (script gen, TTS, Web UI, Script Lab)
- [x] Note database migration (script_mode, voice_1_id, voice_2_id fields)
- [x] List new API endpoints (/api/script-lab/preview)
- [x] List new UI components (Topics page, Script Lab)

**Files**: `VERSION_GUIDE.md`

**Estimated Time**: 15 minutes
**Actual Time**: 20 minutes

---

### Task 5.4: Update CLAUDE.md
- [x] Add section on dialogue mode configuration
- [x] Document audio tags usage ([excited], [thoughtful], etc.)
- [x] Add examples of dialogue vs narrative scripts
- [x] Update pipeline architecture (dialogue/narrative routing)

**Files**: `CLAUDE.md`

**Estimated Time**: 30 minutes
**Actual Time**: 25 minutes

---

### Task 5.5: Update README.md
- [x] Add multi-voice dialogue to features list
- [x] Update TTS section with dialogue/narrative modes
- [x] Add voice configuration instructions (Web UI Topics page)
- [x] Add comprehensive Multi-Voice Dialogue section with examples

**Files**: `README.md`

**Estimated Time**: 15 minutes
**Actual Time**: 20 minutes

---

### Task 5.6: Phase 5 Documentation Review
- [x] Review all documentation for accuracy
- [x] Verify all examples are correct
- [x] Verify file references are accurate

**Estimated Time**: 15 minutes
**Actual Time**: 10 minutes

**Phase 5 Total Time**: ~2 hours

---

## Phase 6: Version Bump & Deployment

**Goal**: Version bump, commit, and push all changes

**Status**: ⏳ NOT STARTED

### Task 6.1: Version Bump
- [ ] Update `web_ui_hosted/app/version.ts` to v1.80 (or appropriate)
- [ ] Update `VERSION_GUIDE.md` with release notes

**Files**: `web_ui_hosted/app/version.ts`, `VERSION_GUIDE.md`

**Estimated Time**: 5 minutes

---

### Task 6.2: Commit Changes
- [ ] Stage all modified files
- [ ] Review diff for any unintended changes
- [ ] Create commit message with feature summary
- [ ] Include version in commit message

**Estimated Time**: 10 minutes

---

### Task 6.3: Push and Deploy
- [ ] Push to GitHub
- [ ] Verify GitHub Actions pass
- [ ] Verify Vercel deployment succeeds
- [ ] Test production Web UI

**Estimated Time**: 15 minutes

---

### Task 6.4: Post-Deployment Testing
- [ ] Load production Web UI
- [ ] Verify Topics page loads
- [ ] Verify Script Lab works
- [ ] Run test digest generation
- [ ] Listen to generated audio

**Estimated Time**: 20 minutes

**Phase 6 Total Time**: ~50 minutes

---

## Summary

### Total Estimated Time by Phase

| Phase | Focus | Estimated Time | Actual Time | Status |
|-------|-------|----------------|-------------|--------|
| **Phase 1** | Script Generation | ~3.5 hours | 2.5 hours | ✅ COMPLETED |
| **Phase 2** | Audio Generation | ~6 hours | 3.5 hours | ✅ COMPLETED |
| **Phase 3** | Topics Page UI | ~4.5 hours | 2.5 hours | ✅ COMPLETED |
| **Phase 4** | Script Lab UI | ~3 hours | 3.25 hours | ✅ COMPLETED |
| **Phase 5** | Integration Testing | ~2 hours | - | ⏳ NOT STARTED |
| **Phase 6** | Deployment | ~1 hour | - | ⏳ NOT STARTED |
| **TOTAL** | | **~20 hours** | **11.75 hours** | 🟡 **IN PROGRESS** |

### Critical Dependencies

- Phase 2 requires Phase 1 complete (needs dialogue scripts to test)
- Phase 3 & 4 can be done in parallel after Phase 2
- Phase 5 requires all phases complete
- Phase 6 requires Phase 5 complete

### Testing Checkpoints

After each phase, we will:
1. ✅ Run phase-specific tests
2. ✅ Verify outputs match expectations
3. ✅ Fix any issues before proceeding
4. ✅ Update this document with results

---

## Progress Log

### 2025-11-10 (Night) - PHASE 4 COMPLETE
- ✅ **Phase 4 COMPLETE**: Web UI - Script Lab Preview (v1.84)
- ✅ Created `scripts/generate_preview_script.py` standalone script
- ✅ Script accepts JSON input via stdin with topic_name and instructions_md
- ✅ Fetches scored episodes from database for selected topic
- ✅ Calls ScriptGenerator with custom instructions (if provided)
- ✅ Returns JSON with script, char_count, word_count, episode_count, mode
- ✅ Updated `/api/script-lab` route to spawn Python subprocess
- ✅ API uses venv Python 3.13 for proper environment isolation
- ✅ Added preview stats display to Script Lab page UI
- ✅ Shows: Mode (dialogue/narrative), Episodes, Chars, Words
- ✅ Tested: Generated 24,494 char dialogue script from 3 CO episodes
- ✅ Fixed mode detection for both colon and bracket speaker formats
- ✅ Updated version to v1.84
- ✅ Committed and pushed to GitHub
- 📝 Ready for Phase 5: Integration Testing & Documentation

### 2025-11-10 (Night) - PHASE 3 COMPLETE
- ✅ **Phase 3 COMPLETE**: Web UI - Topics Page (v1.82)
- ✅ Created `/api/voices` endpoint to fetch ElevenLabs voices
- ✅ Updated `TopicRecord` interface with use_dialogue_api, dialogue_model, voice_config fields
- ✅ Updated Topics API (GET/POST) to read and save new dialogue fields
- ✅ Created VoiceSelector component for single-voice selection with voice library
- ✅ Created MultiVoiceConfig component for SPEAKER_1/SPEAKER_2 configuration
- ✅ Redesigned Topics page UI to card-based layout
- ✅ Added TTS Model dropdown (Turbo v2.5, v3)
- ✅ Added Dialogue Mode toggle with conditional voice selector rendering
- ✅ Tested API endpoints: Topics API returns all new fields correctly
- ✅ Tested API endpoints: Voices API returns 31 ElevenLabs voices
- ✅ Verified page compilation with no TypeScript errors
- ✅ Updated version to v1.82
- 📝 Ready for browser-based UI testing and database save verification

### 2025-11-10 (Late Evening) - PHASE 2 COMPLETE
- ✅ **Phase 2 COMPLETE**: Audio Generation Backend (v1.81)
- ✅ Created dialogue_chunker.py module with DialogueChunk dataclass
- ✅ Implemented chunk_dialogue_script() with intelligent sentence-boundary splitting
- ✅ Added _parse_dialogue_script() to map speakers to voice IDs
- ✅ Added _call_text_to_dialogue_api() with exponential backoff retry logic
- ✅ Implemented _concatenate_audio_chunks() using ffmpeg concat demuxer
- ✅ Created _generate_chunked_dialogue_audio() orchestration method
- ✅ Added progress tracking with JSON-based error recovery
- ✅ Updated generate_audio_for_digest() with dialogue/narrative routing
- ✅ Fixed critical regex bug: Changed $ to \Z for proper turn parsing
- ✅ Enhanced chunker to split oversized turns at sentence boundaries
- ✅ End-to-end testing: Generated 28-minute test MP3 from 21,495 chars
- ✅ Verified all chunks stay under 3,000 char API limit
- ✅ Updated Community Organizing instructions for detailed episode context
- ✅ Committed and pushed to GitHub (commit bce752d)
- 📝 Ready to begin Phase 3: Web UI - Topics Page

### 2025-11-10 (Evening)
- ✅ **Phase 1 COMPLETED**: Script Generation Backend
- ✅ Added dialogue mode detection methods to ScriptGenerator
- ✅ Implemented _generate_dialogue_script() with audio tags (15-20k chars)
- ✅ Implemented _generate_narrative_script() with TTS optimization (10-15k chars)
- ✅ Updated generate_script() routing logic
- ✅ Updated Topic dataclass in models.py with new fields
- ✅ Updated TopicRepository to read new fields from database
- ✅ Updated ConfigManager to pass new fields through config dict
- ✅ Verified routing: Community Organizing → dialogue, others → narrative
- 📝 Ready to begin Phase 2: Audio Generation

### 2025-11-10 (Morning)
- ✅ Created task list document
- ✅ Completed database schema migration
- ✅ Updated SQLAlchemy models
- ✅ Configured all topic voices in database

---

## Notes & Decisions

**Audio Tags Decision**: Use liberally in dialogue scripts for emotional warmth and expression.

**Character Limits**:
- Dialogue scripts: 15,000-20,000 characters
- Narrative scripts: 10,000-15,000 characters
- v3 chunks: 2,800 characters max (under 3,000 limit)

**Cost Estimates**:
- Community Organizing: ~$5/digest (7 chunks × v3 pricing)
- Estimated monthly: ~$50-100 (infrequent generation)

**Voice IDs**:
- Young Jamal: `6OzrBCQf8cjERkYgzSg8`
- Dakota H: `P7x743VjyZEOihNNygQ9`
- Nayva: `h2dQOVyUfIDqY2whPOMo`
- Zuri: `C3x1TEM7scV4p2AXJyrp`
