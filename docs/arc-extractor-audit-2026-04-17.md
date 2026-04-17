# Story-arc extractor audit — 2026-04-17

## Question investigated

Two codebases — podcast (`podcast-pipeline`) and ainewsletter (`AInewsletter`) —
both share the same Supabase DB and both contain a `StoryArcExtractor` class
writing to the `story_arcs` table. Is duplicate extraction happening? Do we
have conflicting rows?

## Finding: no current duplication

**Only one arc extractor is actively writing**: the podcast pipeline's
`StoryArcExtractor` (migrated to `claude -p` in v3.31), invoked as part of
the daily 9 PM PT pipeline. All 106 current AI&Tech story arcs were written
by this path; most recent writes are 2026-04-17 04:02–05:01 UTC (matching
the overnight podcast cron).

**ainewsletter's `StoryArcExtractor` is dormant**:
- `/srv/projects/AInewsletter/scripts/cron_newsletter.sh` (Friday 9 AM PT)
  runs only `generate_newsletter.py` + `send_newsletter.py`. No extraction.
- `/srv/projects/AInewsletter/scripts/run_youtube_transcripts.py` does call
  `extract_and_store_story_arcs()`, but it's not in et01's crontab.
- Last run: 2026-02-20 (2 months ago), based on `logs/cron_youtube.log` mtime.
- `scripts/cron_youtube_transcripts.sh` wrapper exists but is orphaned.

**ainewsletter's newsletter generation reads `story_arcs`**, does not write:
`/srv/projects/AInewsletter/src/newsletter/generator.py:176–214` queries
`story_arcs` filtered by `digest_topic='AI and Technology'` with min 2 events /
2 sources, picks top 3 by recent activity. Pure consumer.

## Recommendation

**Leave as-is**. No active conflict, no data problem. Consolidating would be
premature engineering. If the ainewsletter YouTube pipeline is ever
reactivated, revisit — at that point we'd want to either route its
extraction through the podcast project's code, or explicitly namespace the
arcs (e.g., by `source` column). For now, the podcast project is sole
writer and single source of truth.

## Minor cleanup worth doing later (not urgent)

- Delete the orphan wrapper `/srv/projects/AInewsletter/scripts/cron_youtube_transcripts.sh`
  so it doesn't mislead whoever inherits this.
- Or add a commit to the ainewsletter README noting that the YouTube arc
  path is dormant and why.

## Related Task 8 status

Closed. The original concern (duplicate extraction writing conflicting arcs)
turned out not to be a live issue.
