# Publishing & TTS Workflow Refactor Plan

## Problem Summary

GitHub Actions workflows create files (RSS feeds, MP3s) in ephemeral environments but never persist them back to the repository. This affects multiple phases:

1. **Publishing Phase**: RSS feed generation works but files aren't committed back
2. **TTS Phase**: MP3 files are generated and uploaded to GitHub releases but not saved to `data/completed-tts/current/`
3. **Other Phases**: May also need write permissions for intermediate files

**Root Causes**:
1. GitHub Actions workflows lack write permissions to commit back to repository
2. Generated files exist only in ephemeral GitHub Actions environment and are lost
3. Git configuration missing for proper commits from workflows
4. No commit steps to persist generated artifacts

## Phase 1: Fix Publishing Workflow (COMPLETED ✅)

### 1. Add Repository Write Permissions
**File**: `.github/workflows/phase-publishing.yml`
**Status**: ✅ COMPLETED
**Action**: Added permissions section at job level (after line 30):
```yaml
permissions:
  contents: write    # For git push operations
  packages: write    # For GitHub releases
```

### 2. Fix Dry Run Default
**File**: `.github/workflows/phase-publishing.yml`
**Status**: ✅ COMPLETED
**Action**: Changed line 21 from `default: "true"` to `default: "false"`

### 3. Add Git Configuration
**File**: `.github/workflows/phase-publishing.yml`
**Status**: ✅ COMPLETED
**Action**: Added git configuration step after checkout

### 4. Simplify Bash Script Logic
**File**: `.github/workflows/phase-publishing.yml`
**Status**: ✅ COMPLETED
**Action**: Simplified publishing phase step to remove DRY_RUN parsing

**Result**: Publishing workflow now successfully commits RSS feeds to repository and Vercel auto-deploys them.

## Phase 2: Fix Publishing Script Logic (COMPLETED ✅)

### 1. Debug RSS Commit Logic
**File**: `scripts/run_publishing.py`
**Status**: ✅ COMPLETED
**Action**: Added debug logging to track GitHub Actions detection and decision flow

### 2. Verify Environment Variable Detection
**File**: `scripts/run_publishing.py`
**Status**: ✅ COMPLETED
**Action**: Fixed GitHub Actions detection logic and added logging

### 3. Fix Git Authentication
**File**: `scripts/run_publishing.py`
**Status**: ✅ COMPLETED
**Action**: Updated git push to use GITHUB_TOKEN authentication

**Result**: Publishing script now correctly detects GitHub Actions environment and commits RSS feeds.

## Phase 3: Fix TTS Workflow (COMPLETED ✅)

### 1. Add Repository Write Permissions
**File**: `.github/workflows/phase-tts.yml`
**Status**: ✅ COMPLETED
**Action**: Add permissions section at job level (after line 26):
```yaml
permissions:
  contents: write    # For git push operations
  packages: write    # For GitHub releases
```

### 2. Add Git Configuration
**File**: `.github/workflows/phase-tts.yml`
**Status**: ✅ COMPLETED
**Action**: Add new step after checkout (after line 42):
```yaml
- name: Configure git for commits
  run: |
    git config --global user.name "Paul Brown"
    git config --global user.email "brownpr0@gmail.com"
```

### 3. Fix Workflow Title
**File**: `.github/workflows/phase-tts.yml`
**Status**: ✅ COMPLETED
**Action**: Change line 25 from "Run TTS Phase (Dry Run)" to "Run TTS Phase"

### 4. Add Commit Step for Generated MP3s
**File**: `.github/workflows/phase-tts.yml`
**Status**: ✅ COMPLETED
**Action**: Add new step before artifact collection (around line 171):
```yaml
- name: Commit MP3 files to repository
  if: success() && inputs.dry_run != 'true'
  run: |
    # Check if any MP3 files were generated
    if [ -d "data/completed-tts" ] && [ "$(ls -A data/completed-tts/*.mp3 2>/dev/null)" ]; then
      # Move files to current directory
      mkdir -p data/completed-tts/current
      mv data/completed-tts/*.mp3 data/completed-tts/current/ 2>/dev/null || true

      # Add and commit the MP3 files
      git add data/completed-tts/current/*.mp3
      git commit -m "Add generated TTS MP3 files - $(date +'%Y-%m-%d %H:%M:%S')

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>" || echo "No changes to commit"

      # Push using GITHUB_TOKEN
      git push https://x-access-token:${{ secrets.GITHUB_TOKEN }}@github.com/${{ github.repository }}.git main
    else
      echo "No MP3 files generated to commit"
    fi
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 5. Verify Persistence in GitHub Actions (Simulator Workflow)
**File**: `.github/workflows/tts-simulator-commit.yml`
**Status**: ✅ COMPLETED
**Action**: Added a simulator workflow that creates placeholder MP3 files without external TTS calls, publishes them to a GitHub release, commits the files back to `data/completed-tts/current/`, and updates both RSS feeds. This provides an end-to-end safety harness for validating persistence changes.

## Phase 4: Consider Other Workflows (TODO)

### Workflows That May Need Write Permissions:
1. **Digest Phase**: May want to save generated scripts to repository
   - Status: ⏳ Evaluate if needed
   - File: `.github/workflows/phase-digest.yml`

2. **Audio Phase**: May want to save transcripts or audio chunks
   - Status: ⏳ Evaluate if needed
   - File: `.github/workflows/phase-audio.yml`

3. **Scoring Phase**: Probably doesn't need file persistence (database only)
   - Status: ✅ No changes needed

4. **Discovery Phase**: Probably doesn't need file persistence (database only)
   - Status: ✅ No changes needed

## Phase 5: Future Architecture Considerations (Hold for Later)

### Single Orchestrated Workflow Option
- **Pros**: Eliminates data passing between workflows, ensures atomicity
- **Cons**: Longer execution time, harder to debug individual phases
- **Implementation**: Create `full-pipeline.yml` that runs all phases sequentially
- **Data Flow**: Discovery → Audio → Scoring → Digest → TTS → Publishing in single run

### Alternative Storage Strategies
- Store RSS content in database alongside metadata
- Use GitHub Pages for RSS hosting
- External blob storage (S3, etc.) for persistence

### Workflow Isolation vs Integration
- Current: Phase-specific workflows with artifacts for data passing
- Alternative 1: Single long-running workflow
- Alternative 2: Better artifact-based data passing between phases
- Alternative 3: Database-centric approach with minimal file system usage

## Execution Steps

1. **Immediate fixes (Phase 1)**:
   - Update workflow permissions
   - Fix dry_run default
   - Add git configuration
   - Simplify bash logic

2. **Debug and fix (Phase 2)**:
   - Add logging to understand execution path
   - Fix RSS commit logic
   - Test git operations

3. **Validate**:
   - Run publishing workflow
   - Verify RSS file gets committed to repository
   - Confirm Vercel deployment triggers
   - Check RSS feed updates at podcast.paulrbrown.org

## Success Criteria

- [ ] Publishing workflow can commit files back to repository
- [ ] RSS feed gets updated in both `data/rss/` and `public/` directories
- [ ] Vercel automatically deploys updated RSS feed
- [ ] Daily digest episodes appear in RSS feed at podcast.paulrbrown.org
- [ ] GitHub releases continue to work for MP3 storage

## Context-Clearing Execution Prompt

After clearing context, use this prompt to continue:

```
I need to fix the GitHub Actions TTS workflow that generates MP3 files but never commits them to the repository. The workflow successfully generates MP3s and uploads to GitHub releases, but the files don't appear in data/completed-tts/current/ in the repository.

The publishing workflow has already been fixed (Phase 1 & 2 in @publish-refactor.md are COMPLETED ✅).

Now fix the TTS workflow (Phase 3 in @publish-refactor.md):

1. Add write permissions to .github/workflows/phase-tts.yml (contents: write, packages: write) after line 26
2. Add git configuration step with user: "Paul Brown" email: "brownpr0@gmail.com" after line 42
3. Change workflow title from "Run TTS Phase (Dry Run)" to "Run TTS Phase" on line 25
4. Add a new step to commit MP3 files before artifact collection (around line 171) that:
   - Checks for generated MP3s in data/completed-tts/
   - Moves them to data/completed-tts/current/
   - Commits and pushes them using GITHUB_TOKEN

The goal is to persist TTS-generated MP3 files in data/completed-tts/current/ in the repository.

Files to modify: .github/workflows/phase-tts.yml
Check @publish-refactor.md Phase 3 for the complete plan with exact code snippets.

After completing Phase 3, update the status markers in @publish-refactor.md from ⏳ TODO to ✅ COMPLETED for each completed task.
```
