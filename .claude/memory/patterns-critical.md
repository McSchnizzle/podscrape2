<!--
Critical Patterns for RSS Podcast Digest System
Stack: Python 3.13+, Next.js, PostgreSQL (Supabase), OpenAI, ElevenLabs
-->

### Top Failure Patterns

1. **FFmpeg Subprocess Hang (CRITICAL)**
   - Trigger: FFmpeg hangs in cron/background without TTY
   - Prevention: ALWAYS use `stdin=subprocess.DEVNULL` in subprocess calls to ffmpeg/ffprobe

2. **Environment Config Silently Failing**
   - Trigger: Missing API keys causing partial failures
   - Prevention: Fail fast! Run `scripts/doctor.py` to validate. No fallbacks - RED status in UI for missing config.

3. **Version Not Bumped**
   - Trigger: Committing without updating version
   - Prevention: MUST update version in `web_ui_hosted/app/version.ts` (+0.01) before EVERY commit

### Quick Reference

| Situation | Do This | Not This |
|-----------|---------|----------|
| Python commands | `python3`, `pip3` | `python`, `pip` |
| Timeout on macOS | `gtimeout` | `timeout` |
| Topic config | Edit in database `topics` table | Filesystem files |
| Test feeds | Use real RSS feeds listed in CLAUDE.md | Mock data |

### Project-Specific Gotchas

- Pipeline: Discovery → Audio → Digest → TTS → Publishing → Retention
- Cron runs on et01 server (not GitHub Actions since v2.72)
- Two script modes: dialogue (2 speakers, 15-20k chars) vs narrative (single voice, 10-15k chars)
- Score threshold: 0.65 for inclusion
- Episode status flow: pending → processing → transcribed → scored → digested
- RLS enabled on ALL tables - use service role for backend operations
- Audio chunks: 3 minutes for optimal ASR performance


### Learned Patterns (2026-02-20 08:08)

- **Gotcha**: now that i think about it, the only reason that project's youtube transcripts are separate from your rss feeds was because your feed cron job used to 


### Learned Patterns (2026-02-20 08:08)

- **Gotcha**: now that i think about it, the only reason that project's youtube transcripts are separate from your rss feeds was because your feed cron job used to 


### Learned Patterns (2026-02-20 08:26)

- **Error encountered**: ### Summary of the Issue
- **Error encountered**: involves episodes with very short transcripts (potentially as low as 241 characters) being accepted into the pipeline, scored by GPT, and included in 


### Learned Patterns (2026-02-20 09:25)

- **Error encountered**: with exit code 1</summary>
- **Gotcha**: to not corrupt the other data
