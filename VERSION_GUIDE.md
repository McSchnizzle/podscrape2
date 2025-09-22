# Version Management Guide

## Current Version: 0.75

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

Major milestones:
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