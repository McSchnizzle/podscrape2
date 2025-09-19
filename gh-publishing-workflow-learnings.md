# GitHub Publishing Workflow Learnings

## Why GitHub Releases Are a Fit
- GitHub’s documentation recommends Releases for distributing compiled or binary assets; they sit behind a CDN and avoid bloating commit history.
- Artifacts generated inside GitHub Actions expire after 90 days, so they are useful for debugging but not for podcast distribution.
- Ordinary git blobs are capped at 100 MB and cloning large binaries slows local workflows, so Releases provide a better long-term store for MP3s.

## End-to-End Persistence Checklist
- The simulator workflow generates placeholder audio with FFmpeg inside Actions; duration is configurable (we’re using 600 s to exercise >2 MB downloads).
- After generation the workflow pushes the MP3 to the `daily-YYYY-MM-DD` GitHub Release **and** commits the file under `data/completed-tts/current/` so the repo stays in sync with what publishing expects.
- The same workflow updates `data/rss/daily-digest.xml`, `public/daily-digest.xml`, and mirrors them to `data/rss/test-feed.xml` / `public/test-feed.xml`. That test feed is deployed to `podcast.paulrbrown.org/test-feed.xml`, giving us a live proof point without touching the production feed.

## Lessons from the Simulator Runs
- Very small placeholder MP3s (~5 KB) surfaced “file too small” errors in podcast clients; generating a several-minute tone (~2 MB+) avoids that and exercises the real download path.
- Keeping RSS edits minimal (string splicing instead of regenerating the entire document) makes review diffs readable and avoids churn when only the newest `<item>` changes.
- Branch targeting matters: pushing to a dedicated `simulated-tts` branch keeps repeated experiments isolated, but the test run against `main` proved we can commit and deploy in one flow when needed.

## Next Steps for Production
- Mirror the simulator pattern in the real TTS workflow: generate audio, push to Release, commit to `data/completed-tts/current/`, update RSS, and deploy `public/daily-digest.xml`.
- Consider parameterizing release tags or branch targets so we can run dry-runs on a sandbox branch before touching `main`.
- Retain the simulator workflow as a regression harness—any future changes to publishing can exercise it without burning ElevenLabs/GPT quota.
