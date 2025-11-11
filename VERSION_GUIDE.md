# Version Management Guide

## Current Version: 1.84

This document outlines the version management process for the RSS Podcast Transcript Digest System.

## Version Increment Process

**IMPORTANT**: Update the version number in `web_ui_hosted/app/version.ts` on every commit.

### Version Numbering Scheme

- **Major versions** (x.0): Significant system changes, new phases
- **Minor versions** (0.x): Feature additions, major improvements
- **Patch versions** (0.x.y): Bug fixes, minor improvements (future use)

### When to Increment

**Every commit should increment the version by 0.01**

Examples:
- Current: 0.75
- Next commit: 0.76
- Following commit: 0.77

### Process

1. **Before committing**, update `VERSION` in `web_ui_hosted/app/version.ts`:
   ```typescript
   export const VERSION = "0.76"; // Increment from previous
   ```

2. **Include version in commit message**:
   ```
   feat: add footer component with version tracking (v0.76)
   ```

3. **The footer will automatically display**:
   - Version number (from version.ts)
   - Short commit hash (from Git)
   - Build timestamp (from deployment)

## Footer Information

The footer displays across all pages:
- **Version**: Set in `web_ui_hosted/app/version.ts`
- **Commit Hash**: Automatically from Git (VERCEL_GIT_COMMIT_SHA, GITHUB_SHA)
- **Build Time**: Set during build process (BUILD_TIME environment variable)

## File Locations

- **Version config**: `web_ui_hosted/app/version.ts`
- **Footer component**: `web_ui_hosted/components/Footer.tsx`
- **Build config**: `web_ui_hosted/next.config.js`
- **Package scripts**: `web_ui_hosted/package.json`

## Environment Variables

The following environment variables are used for version display:

- `BUILD_TIME`: Build timestamp (set by build script)
- `VERCEL_GIT_COMMIT_SHA`: Commit hash on Vercel
- `GITHUB_SHA`: Commit hash in GitHub Actions
- `COMMIT_SHA`: Fallback commit hash

## Example Footer Output

```
RSS Podcast Digest System | v0.75     Build: a1b2c3d | Sep 21, 2025, 8:30 PM PDT
```

## Version History Tracking

### Multi-Voice Dialogue Feature (v1.79 - v1.84)

This major feature release added comprehensive multi-voice dialogue support to the podcast digest system. Key capabilities:

**Architecture Changes**:
- Database schema updates: Added `script_mode`, `voice_1_id`, `voice_2_id`, `dialogue_model` fields to `topics` table
- Script generation routing: Automatic detection of dialogue vs narrative mode per topic
- Audio generation: Integration with ElevenLabs Text-to-Dialogue API (v3) with intelligent chunking
- Web UI updates: Complete Topics page redesign with voice configuration and Script Lab preview

**Technical Implementation**:
- **Script Generation**: 15-20k character dialogue scripts with SPEAKER_1/SPEAKER_2 format and audio tags
- **Audio Chunking**: Smart splitting of long dialogues into ~3k character chunks at speaker boundaries
- **Voice Mapping**: Database-driven voice configuration with speaker personality support
- **TTS Optimization**: Narrative mode includes text normalization and TTS-friendly formatting
- **API Integration**: Chunked calls to Text-to-Dialogue API with automatic audio concatenation

**Database Migration**:
- Added `script_mode` enum: 'dialogue' or 'narrative'
- Added voice configuration fields for dual-voice support
- Added `dialogue_model` for GPT model selection
- Maintained backward compatibility with existing topics

**New API Endpoints**:
- `/api/script-lab/preview`: Real-time script generation preview with OpenAI
- `/api/topics`: Enhanced with voice configuration support

**New UI Components**:
- Topics page: Voice selection, dialogue model picker, instructions editor
- Script Lab: Interactive preview with real episode data
- Voice configuration: Dropdown selectors for Voice 1 and Voice 2

### Recent Versions (Multi-Voice Dialogue Implementation)

**v1.84** (2025-11-10) - Phase 4: Script Lab Preview
- Implemented Script Lab preview with OpenAI integration
- Added `/api/script-lab/preview` endpoint for real-time script generation
- Integrated with Web UI Topics page for instant script preview
- Added comprehensive error handling and loading states
- Fixed TypeScript type issues in script preview action

**v1.83** (2025-11-10) - Cache & Data Fixes
- Added cache-busting to Episodes page to prevent stale data
- Fixed stale data issues in Web UI

**v1.82** (2025-11-10) - Phase 3: Web UI Multi-Voice Configuration
- Implemented Topics page with multi-voice dialogue configuration
- Added voice selection dropdowns for Voice 1 and Voice 2
- Added dialogue model selection (gpt-4o, gpt-4o-mini)
- Added instructions_md editor with markdown support
- Added Script Lab preview button for instant script testing
- Created comprehensive Web UI for topic management

**v1.81** (2025-11-10) - Phase 2: Multi-Voice TTS with Chunking
- Implemented Text-to-Dialogue API integration with ElevenLabs v3
- Added dialogue script chunking (splits 20k scripts into ~3k chunks)
- Implemented audio concatenation with ffmpeg
- Added speaker continuity tracking across chunks
- Fixed database bugs in dialogue processing
- Completed end-to-end audio generation pipeline

**v1.80** (2025-11-10) - Phase 1: Multi-Voice Dialogue Script Generation
- Added dialogue mode detection based on topic configuration
- Implemented dialogue script generation with SPEAKER_1/SPEAKER_2 format
- Added audio tags support ([excited], [thoughtful], [serious], etc.)
- Created narrative script generation with TTS optimization
- Added routing logic: dialogue mode vs narrative mode
- Updated Python version requirement to 3.13+
- Character-based length targets (15-20k for dialogue, 10-15k for narrative)

**v1.79** (2025-11-10) - Multiple Digests Per Day
- Fixed digest generation to allow multiple digests per day
- Improved episode checking to detect new episodes before regenerating digests

### Earlier Milestones
- **0.75**: Added comprehensive footer with version tracking
- **0.74**: Implemented feeds API caching
- **0.73**: Completed performance optimization
- **0.72**: Resolved multi-topic processing
- **0.71**: Completed topics database migration
- **0.70**: Completed settings bridge

## Future Considerations

- Consider semantic versioning (1.0.0) for production release
- Automated version bumping via CI/CD
- Version-based feature flags
- Release notes generation