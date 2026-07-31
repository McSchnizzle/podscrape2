# Test feeds

Moved out of `CLAUDE.md` (2026-07-31).

**Never use mock data or fabricated RSS.** Real feeds surface actual CDN
behaviour, network faults, redirect chains and malformed audio that mocks hide
by construction -- and those are the failures that break the pipeline in
production.

| Feed | URL |
|---|---|
| The Bridge with Peter Mansbridge | https://feeds.simplecast.com/imTmqqal |
| Anchor | https://anchor.fm/s/e8e55a68/podcast/rss |
| The Great Simplification | https://thegreatsimplification.libsyn.com/rss |
| Movement Memos | https://feeds.megaphone.fm/movementmemos |
| Kultural | https://feed.podbean.com/kultural/feed.xml |

## Phase tests

```bash
python3 test_phase2_simple.py        # RSS parsing
python3 test_phase3.py               # transcription
python3 test_phase4.py               # scoring
python3 test_phase5.py               # script generation
python3 test_phase6_integration.py   # TTS

python3 test_full_pipeline_integration.py
python3 test_database_integration.py
```

## Maintenance helpers

```bash
python3 rescore_episodes.py                  # rescore against new topics/thresholds
python3 reset_latest_episode.py              # reset status for a retest
python3 transcribe_episode.py <episode_guid> # transcribe one episode

python3 run_publishing_pipeline.py --days-back 7   # retry recent publishes
gh release list --repo $GITHUB_REPOSITORY
curl -s https://podcast.paulrbrown.org/daily-digest.xml | head -20
```
