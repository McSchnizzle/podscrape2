# Hot-Topic Mechanism Deprecation — Tracking Doc

**Purpose**: Track the two-stage deprecation of the `is_hot` / `hot_briefing` /
`saturation_score` mechanism in `src/generation/script_generator.py`. This doc
exists so that in ~1 week we remember exactly what we changed, how to evaluate
whether it worked, and how to roll back if it didn't.

## Background

As of v3.36 (2026-04-16), the pre-generation dedup (`src/generation/transcript_dedup.py`)
runs a fresh LLM scan of the last 5 digests on every pipeline run to identify
**saturated topics** (stories covered 3+ times). Those topics get aggressive
background-stripping instructions inside the dedup prompt, so the transcripts
that reach the script generator are already stripped of redundant context.

Before v3.36, we relied on three separate prompt-builder paths in
`script_generator._build_story_arc_context()` (around lines 641–794) to tell
the generator how to handle tracked stories:

1. **WELL-COVERED STORIES section** — pulled `saturation_score >= 0.9` arcs
   from the `story_arcs` table and listed them in the prompt with instructions
   to "focus on new info, note coverage continues if nothing new."
2. **HOT STORY BRIEFINGS section** — pulled `is_hot=true` arcs with their
   `hot_briefing` text, injected the briefing so the generator had accumulated
   context for tracked stories.
3. **Hot-arc merging + grounding bypass** — hot arcs were merged into the
   digest-candidate arc list regardless of episode grounding, so they always
   appeared in the prompt even if no today's-episode cited them.

After v3.36, (1) is functionally redundant with dedup's evergreen detection —
both identify 3+ coverage, but dedup's version is LLM-fresh per run and
operates on the actual transcript text. (2) is belt-and-suspenders — with
background stripped from transcripts, the audience's memory of prior digests
supplies context. (3) becomes unnecessary once (1) and (2) are removed.

## Stage 1 (THIS STAGE): Stop reads, keep columns

**Date committed**: 2026-04-17
**Commit SHA**: _to be filled in at commit_
**Version**: v3.38 (ep 611 fix bumped to v3.37; this stage is v3.38)
**Earliest Stage 2 review date**: 2026-04-24

**Code changes** in `src/generation/script_generator.py`:
- Remove the WELL-COVERED STORIES prompt section (around lines 739–758).
- Remove the HOT STORY BRIEFINGS prompt section (around lines 695–717) and
  the `hot_briefing_section` concatenation logic.
- Remove the `hot_flag_arcs` query and the hot-arc merge into `arcs` (lines
  647–660).
- Remove the grounding-bypass for hot arcs (lines 670–674).
- Keep the general story-arc-context injection (developing stories list,
  `_format_arc_for_context`) — that's *different* signal, showing what's
  actively unfolding this week. We are NOT removing arc awareness from the
  prompt entirely.

**What we are deliberately leaving in place** (for easy reversal):
- `is_hot`, `hot_briefing`, `retain_until`, `saturation_score` columns on
  `story_arcs`.
- `src/topic_tracking/hot_briefing_generator.py` — still runs, still writes
  `is_hot=true` and populates `hot_briefing` text.
- `src/topic_tracking/topic_extractor.py` auto-promotion logic at ~line 270.
- UI editing in `web_ui_hosted/app/story-arcs/page.tsx:215` and the update API
  at `web_ui_hosted/app/api/story-arcs/arcs/[id]/route.ts:88`.
- `story_arc_repo.cleanup_old_story_arcs()` preserving hot arcs.

**Rationale**: Dropping schema/code is hard to reverse. Removing prompt
sections is a single-file change with a trivial `git revert`. If digest
quality regresses, we can restore the old behavior in minutes without any
data loss.

## Stage 2 (FUTURE): Drop columns, delete code

**Earliest trigger date**: _Stage 1 date + 7 days_
**Review criteria below.** Do NOT proceed to Stage 2 without explicit review.

**If Stage 1 is validated as clean, Stage 2 will**:
1. Write Alembic migration to drop `is_hot`, `hot_briefing`, `retain_until`,
   `saturation_score` columns from `story_arcs`.
2. Delete `src/topic_tracking/hot_briefing_generator.py`.
3. Remove auto-promotion logic from `src/topic_tracking/topic_extractor.py`
   (around line 270).
4. Remove hot-toggle UI from `web_ui_hosted/app/story-arcs/page.tsx`.
5. Remove hot fields from the update API payload in
   `web_ui_hosted/app/api/story-arcs/arcs/[id]/route.ts`.
6. Simplify `story_arc_repo.cleanup_old_story_arcs()` — without `is_hot` /
   `retain_until` checks, cleanup becomes pure age-based (delete orphans >3d,
   delete inactive arcs >7d).
7. Remove `is_hot` / `hot_briefing` from the SQLAlchemy model at
   `src/database/sqlalchemy_models.py`.
8. Update/remove the merge logic at
   `web_ui_hosted/app/api/story-arcs/arcs/merge/route.ts` if it references
   hot fields.
9. Update `.claude/commands/merge-arcs.md` to drop hot-topic steps.

## Review criteria (apply on day 7)

**Proceed to Stage 2 if ALL are true**:
- Daily digests generated between Stage 1 commit date and review date read
  coherently. Tracked stories (Mythos, Glasswing, Muse Spark, etc.) continue
  to appear as continuations — not restarted from scratch.
- No listener-side / Paul-side feedback reporting digests "feel disconnected"
  or "missing the thread" on recurring stories.
- Pipeline logs show dedup's evergreen detection firing on each run and
  producing a reasonable list of saturated topics (grep logs for
  `Evergreen detection: found N saturated topics` where N > 0 most days).
- Post-gen dedup pass (`dedup_pass.py`) is still running and not producing
  a flood of false positives or empty output (grep logs, spot-check a few
  script diffs).

**Do NOT proceed — revert Stage 1 instead if ANY are true**:
- Digests show tracked stories being re-introduced with full background
  paragraphs.
- Paul reads a digest and it feels like the thread got lost on a story he's
  been following.
- Evergreen detection is silently failing (logs show "evergreen detection
  timed out" or "claude -p unhealthy" on more than 2 runs in the period).

## Rollback procedure (if Stage 1 regresses)

```bash
cd /Users/paulbrown/Desktop/coding-projects/podcast
git log --oneline | grep -i "stage 1\|deprecate hot"  # find the Stage 1 commit
git revert <stage-1-sha>
# Bump version in web_ui_hosted/app/version.ts
# Commit + push
ssh et01 'cd /srv/projects/podcast-pipeline && ...'   # redeploy to et01
```

No data migration needed — columns were never dropped in Stage 1.

## Review log

_Append entries here as they happen. Keep the most recent at the top._

- **_TBD Stage 1 commit date_**: Stage 1 deployed. Next review date: _TBD+7_.
