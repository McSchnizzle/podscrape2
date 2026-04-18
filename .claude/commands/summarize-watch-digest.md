# Summarize Watch Digest

Summarize a raw watch-themes digest into shape-C (headline + big story paragraph + "Also this week" bullets) per theme. Iterates freely — each run produces a new version-suffixed file.

## How to iterate

1. Run the skill — produces `-v1.md`
2. Read the output; note what's wrong (too verbose? wrong tone? missing context? too many bullets?)
3. Edit the `SYNTHESIS_PROMPT` string at the top of `scripts/summarize_watch_digest.py`
4. Re-run — produces `-v2.md`
5. Diff the two with `diff data/watch-digests/<date>-summary-v1.md data/watch-digests/<date>-summary-v2.md`
6. Repeat until the output is what you want.

Once dialed in, fold the prompt into `scripts/run_watch_digest.py` as a post-scan synthesis pass, so the weekly cron delivers the summarized version directly.

## Steps

### 1. Run on latest raw digest

```bash
source .venv/bin/activate && python3 scripts/summarize_watch_digest.py
```

Output files land in `data/watch-digests/<date>-summary-vN.md` and `.html`.

### 2. Or run on a specific raw digest

```bash
source .venv/bin/activate && python3 scripts/summarize_watch_digest.py data/watch-digests/2026-04-17-raw.md
```

### 3. Review and iterate

```bash
cat data/watch-digests/2026-04-17-summary-v1.md
# Decide what needs tweaking, edit SYNTHESIS_PROMPT in the script, re-run
diff data/watch-digests/2026-04-17-summary-v1.md data/watch-digests/2026-04-17-summary-v2.md
```

## Output shape (shape C)

Per theme:

```
## Theme name

**[One-sentence headline — dominant story this week.]**

[Single paragraph, 4-8 sentences. Collapses overlapping excerpts into one
coherent narrative. Preserves numbers and direct quotes. Cites episodes
inline in italic parens.]

**Also this week:**
- [Secondary mention] — (*Episode Title*)
- [Secondary mention] — (*Episode Title*)
```

If no meaningful coverage: "No significant coverage this week."
