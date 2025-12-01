/**
 * Version configuration for RSS Podcast Transcript Digest System
 * Update VERSION on every commit to track releases
 */

export const VERSION = "1.99";

// Get build-time information
export const getBuildInfo = () => {
  // Get commit hash from environment variable (set by Vercel/GitHub Actions)
  const commitHash = process.env.VERCEL_GIT_COMMIT_SHA ||
                     process.env.GITHUB_SHA ||
                     process.env.COMMIT_SHA ||
                     'unknown';

  // Get build timestamp (set at build time)
  const buildTime = process.env.BUILD_TIME ||
                    process.env.VERCEL_BUILD_TIME ||
                    new Date().toISOString();

  return {
    version: VERSION,
    commit: commitHash.substring(0, 7), // Short commit hash
    buildTime: buildTime,
    buildDate: new Date(buildTime).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZoneName: 'short'
    })
  };
};

export const getVersionString = () => {
  const info = getBuildInfo();
  return `v${info.version} (${info.commit}) - ${info.buildDate}`;
};