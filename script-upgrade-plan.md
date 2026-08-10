# Script Generation Upgrade Plan (v4.01)

Status: revision 3 — corrected against codex plan-tier review and an
independent adversarial review
Origin: forensic pass on the 2026-08-07 / 2026-08-08 duplicate-intro incident
Scope: the Digest phase (`src/generation/`, `src/topic_tracking/`) plus the dead
and half-wired code it drags along.

**Review changelog.** Two independent reviews (codex plan-tier, adversarial)
converged on the same two blockers in revision 1: F1 was aimed at a helper the
production writer never reads, and F3 blamed a latch both callers already
bypass. Both are corrected below and the fixes moved. Also corrected: F5
credited the variety pass with a capability it does not have, F6's numbers were
cherry-picked, and several counts were wrong. Five new defects surfaced during
review — N1 (sibling dedup inert), N2 (permanent loss on drop), N3 (expansion
episodes bypass dedup), N4 (dedup failure swallowed), N5 (variety/floor
ordering). The adversarial review also **strengthened** the central evidence;
see §1.

---

## 1. What started this

The digest published 2026-08-08 opened with the previous day's cold open, near
word for word:

| | Aug 7 (digest 723) | Aug 8 (digest 724) |
|---|---|---|
| Turn 1 | "A trillion dollar company **just** lost its two most important scientists in one afternoon, and the stock barely moved. *That's the story we're leading with today.*" | "A trillion dollar company lost its two most important scientists in one afternoon, and the stock barely moved." |
| Turn 2 | "[surprised] **Barely moved.** Down four percent. Which given who left is honestly the strangest part of this whole thing." | "[surprised] Down four percent. Which, given who left, is honestly the strangest part of this whole thing." |

Normalized `difflib.SequenceMatcher` on the first two speaker turns: **0.743**.
Across the 14 adjacent pairs in the retained history, normal ranges 0.064 to
0.156. The two digests draw on entirely disjoint episode sets, so this was not
a rerun.

**The repeat runs deeper than the opener.** Measured 723 vs 724 over the first
N turns: n=1 **0.834**, n=2 **0.743**, n=3 **0.820**, n=4 **0.780**, n=5 0.591.
Turn 4 is **verbatim identical** in both scripts ("Start with Google, because
this is the one everyone's going to be talking about."), and turn 3 is the
fixed welcome template differing only in the date. This is not a recycled
cold open, it is a recycled lead segment. Any fix that rewrites only turns 1-2
moves the number below threshold and ships the same digest.

**The decisive fact.** Episode 792 (AI Daily Brief, used Aug 7) says "Google
down 4%" — numerals. Digest 723's *script* renders it spelled out, "Down four
percent". Digest 724 reproduces the **spelled-out** form. None of digest 724's
nine source transcripts contains `four percent`, `4 percent`, `4%`, or `down
four`. So the Aug 8 text matches the prior **script's** rendering, not any
transcript's, which narrows the channel to components that saw digest 723's
script.

Two rival hypotheses are closed: the writer's `claude -p` runs with `--tools ""`
and `--no-session-persistence`, so there is no filesystem or session channel;
and `.claude/commands/generate-digest.md` contains no example cold open.

**Status of the causal claim.** In the writer path exactly one component
received digest 723's full script: `transcript_dedup`, which is handed up to 14
prior scripts most-recent-first (`script_generator.py:2457-2464`), putting
digest 723 at the top of all four chunk prompts for episode 794. That is the
leading explanation. It is still **not proven** — deduped transcripts are not
persisted, and parametric recall cannot be formally excluded. The remediation
is therefore built to be correct either way: it closes the channel *and* adds a
deterministic output check that makes the channel unusable regardless.

---

## 2. Findings

Verified against code, logs, and the live database. Corrections from the codex
review are marked.

### F1 (P0) Two computed prompt inputs are silently dropped, and all three renderers assert everything is new

**Corrected from revision 1.** Revision 1 blamed
`_build_repetition_avoidance_instructions` (`script_generator.py:1009`). That
helper *is* a constant string that discards the saturated topic names it is
handed. But it never reaches the production writer.

The real shape of the defect, across **three** prompt renderers:

| Renderer | Line | Behavior |
|---|---|---|
| `_build_claude_p_dialogue_prompt` (skill-file branch — **production**) | 1052-1073 | Accepts `story_arc_context` and `repetition_instructions` as parameters and **interpolates neither**. Emits its own hardcoded: *"These transcripts have been pre-filtered... Everything provided is NEW material. Cover it all thoroughly."* |
| Hardcoded dialogue fallback | 1186 | Its own copy of the same assertion |
| Narrative | 1633-1637 | Interpolates both helpers — so it gets the revision-1 constant-string bug |

The method's own docstring admits it: `theme_emphasis` "is guaranteed to reach
the model on both branches ... unlike story_arc_context/repetition_instructions
above."

So `_check_topic_repetition` computes the saturated topic names, `generate_script`
builds the block, passes it in, and the dialogue renderer drops it on the floor
— while independently telling Claude that everything in front of it is new.
That assertion is what reached the model on Aug 8. It is false whenever dedup
fails open, and it converts a dedup miss into an instruction to cover the
repeat thoroughly.

### F2 (P0) Pre-gen dedup is generative, and cannot drop a wholly-redundant episode

Aug 8 timeline (`logs/digest_20260808_210223.log`):

- `21:02:40` evergreen detector names the saturated topic outright:
  *"Google DeepMind leadership shakeup: Demis Hassabis steps back from CEO role,
  Jeff Dean departs to launch Discovery Loop."*
- `21:11:39` *"What's behind the Google AI shakeup"* returns
  **106,039 → 104,957 chars, 99% retained**.

Causes, all in `src/generation/transcript_dedup.py`:

1. **The pass rewrites rather than deletes.** It is prompted to "return a
   CLEANED version" — free-form generation. Two Aug 8 episodes came back
   **longer than they went in** (16,415→16,457 and 18,570→18,819; a third was
   near-identical at −18 chars). Nothing constrains the output to material
   present in the input.
2. **Each call sees up to 200,000 chars of verbatim prior digest scripts**
   (`:533`). Combined with (1), this is the leak channel: a generative filter
   holding yesterday's script in context, whose output the writer consumes as
   "the transcript."
3. **Chunking defeats the whole-episode verdict.** `MAX_CHUNK_CHARS = 30_000`
   (`:49`), so the 106k episode became 4 independently-deduped chunks.
   `[NO_NEW_CONTENT]` can only fire per chunk; no call can see the episode as a
   whole adds nothing.
4. **The CRITICAL rule outranks saturated-topic stripping** (`:190`, `:280`).
   An episode entirely *about* the saturated story is all thesis and evidence,
   so nothing qualifies for removal. The ordering is correct for a contrarian
   take on a covered topic and wrong for a straight re-report of it.

Since v3.34 this is the **only** cross-digest repetition defense in the
pipeline (F4), and it fails open by construction.

*Correction from revision 1:* "the largest transcript led because it was
largest" is not supported by code — the writer is not told to rank by length.
Drop that inference; the episode led because it was present, prominent, and
declared new.

### N1 (P0, new — found in review) Same-batch sibling dedup is silently inert

`dedup_episode_batch` appends each episode's deduped output to the **end** of
`prior_content` (`transcript_dedup.py:752`) so later episodes are compared
against earlier ones. But truncation keeps the **first** 200,000 chars
(`:533`).

On Aug 8 every one of the nine episodes logged exactly `200,000 chars prior
context` — the budget was full from episode one. **The sibling comparison never
happened at all**, on any episode, on any recent night. Two episodes covering
the same story on the same day are not deduplicated against each other despite
the code claiming they are.

### N2 (P0, new — found in review) An erroneous drop loses the episode permanently

A zero-char dedup result is treated as a genuine "fully redundant" drop
(`transcript_dedup.py:654`) — explicitly *not* covered by the kanban #2861
below-floor safety net — and the episode is then marked `digested`
(`script_generator.py:2684`) so it never resurfaces. There is no human review
and no reconsideration path. This makes any future "drop the whole episode"
mechanism a permanent-data-loss risk, and invalidates revision 1's claim that
the existing safety net mitigates over-dropping.

### N3 (P1, new — found in review) Expansion-added episodes can reach the writer un-deduped

The pre-dedup pool is capped at `MAX_TRANSCRIPTS = 9`
(`script_generator.py:2418-2423`). If dedup drops episodes, the expansion loop
fetches replacements that were never in that pool, and `:2595` keeps any
episode absent from `deduped_transcript_cache` **with its raw transcript**. The
more dedup drops, the more un-deduped material reaches the writer.

Latent rather than live on Aug 8 — nothing was dropped, and every expansion
episode logged "using pre-deduped transcript". But it is exactly the hole that
any future whole-episode drop mechanism would widen, which is a second reason
that mechanism is deferred (see §3).

### N4 (P1, new — found in review) Dedup failure is swallowed silently

`create_digest:2526` wraps the entire pre-gen dedup batch in a bare
`except Exception`, logs a **warning**, and proceeds with raw transcripts for
all nine episodes. A single failure silently disables the pipeline's only
cross-digest defense for that night, and nothing downstream notices. This is
the same fail-open posture F2 objects to, in a broader form.

### N5 (P1, new — found in review) The restored variety pass would sit on the wrong side of the hard floor

`HARD_FLOOR = 10000` is checked at `:2639`; the empty variety-pass slot is at
`:2630`, **before** it. The pass removes 220-270 chars in practice. A draft at
10,050 chars passes the floor today and would fail after the pass, raising
`ScriptGenerationError` and destroying that night's digest. Restoring the pass
naively introduces a new failure mode.

### F3 (P1) The story-arc subsystem has never influenced a single published episode

**Corrected from revision 1.** The one-way-latch diagnosis was wrong: both
production callers pass `exclude_included=False` (`script_generator.py:753`,
`:962`), and `story_arc_coverage` *is* read, by `get_recently_included_arcs`
(`story_arc_repo.py:352`). The real chain is:

- **The real episode-level arc producer has never run.** It is gated on
  `enable_topic_tracking = True` (`scripts/run_audio.py:1416`), and the only
  active topic ("AI and Technology", `use_dialogue_api=True`) has that flag
  **False**. Every audio log for three days reads "No topics have story arc
  tracking enabled." This, not the v3.27 off-by-one, is the binding constraint.
- There are **two** event producers, not one: `topic_extractor.py:270` calls
  `add_story_arc_event`, which does increment `event_count`
  (`story_arc_repo.py:187`). That is the one gated off above. The reconciler is
  the other, and it only re-reads digest scripts — so repairing it would
  produce arcs whose events derive from the digests they are meant to inform.
  Circular.
- `get_story_arcs_for_digest` gates on `min_events=2` (`story_arc_repo.py:268`)
  while the reconciler seeds exactly **one** synthetic event
  (`digest_arc_reconciler.py:211`), and its match branch logs `"- skipping"`
  and `continue`s (`:181`) without appending. So the reconciler path alone can
  never clear the gate.
- **And even a valid arc could not reach the writer**, because the dialogue
  renderer drops `story_arc_context` (F1).

Live state: **7** arcs, every one at `event_count = 1`, all now carrying
`included_in_digest_id = 725`; 16 `story_arc_coverage` rows. The digest log
reads `No active story arcs found` every single night. Roughly 300 lines plus
three tables that have never affected output.

Also live: arcs 35, 37, 38 are the same story (a compound arc plus its two
halves) — the semantic matcher scores a compound name below threshold against
each of its own halves, and the separate arc deduplicator (threshold 0.75) then
reports "No duplicate arcs found."

*Correction from revision 1:* the claim that arcs get marked on a bare `openai`
token was wrong. `_arc_matches_script` (`:933-937`) already requires 2+
substantive terms, and all 7 arcs matched on 2+. "Tighten the matching" is not
a needed fix.

### F4 (P1) No check ever runs on the finished script

`_run_dedup_pass_with_retry` (compare the finished draft against the last 8
digests) was removed from `create_digest` in v3.34 (`aed4f71`, 2026-04-12) on
the bet that pre-gen dedup replaces it. It, `dedup_pass.py`, and
`transcript_scrubber.scrub_episodes` survive with **only test callers**. The
whole `Dedup` settings category in `web_config.py` is likewise read only by
that dead function.

The bet lost on Aug 8. `script_content_predupe` is NULL on every digest as a
side effect (`script_generator.py:2663` compares two variables that are always
equal).

### F5 (P1) Structural variety never runs on the shipped script

`script_generator.py:2630-2632` (`ae7356b`, v3.48, 2026-04-24) is a comment
promising a final variety pass, followed by no code. Measured:

| night | expansion iterations | variety passes completed |
|---|---|---|
| Aug 6 | 4 | 1 |
| Aug 7 | 5 | 1 |
| Aug 8 | 4 | 1 |
| Aug 9 | 1 | 1 |

The single pass always runs on the **initial draft**, which the expansion loop
then throws away and regenerates. Every digest that expanded has shipped
unvaried since 2026-04-24.

*Correction from revision 1:* this pass could **not** have caught the duplicate
intro. Its prompt sees only the current script, with no prior-digest context,
and is told to preserve facts, structure and turn count (`:1489`). Restore it
because the anti-AI rhythm work is silently not happening, not as an
anti-repetition defense. Note also it hard-requires `SPEAKER_1`/`SPEAKER_2` in
its output (`:1543`), so it no-ops on narrative topics.

### F6 (P2) The expansion loop regenerates the whole script per added episode

`TARGET_CHARS = 25000` and `MAX_TRANSCRIPTS = 9` are hardcoded
(`script_generator.py:2411`). Each iteration adds **one** episode and
regenerates the entire script from scratch (~90s per `claude -p` call),
discarding the previous one. Aug 8: five regenerations, four discarded.

*Correction from revision 1:* the target is **not** unreachable and the loop
does **not** always run to the cap. Six of the 15 retained digests exited on
`TARGET_CHARS` below the episode cap (711: 5 eps/26,733; 713: 4/30,155;
714: 7/26,956; 715: 6/29,412; 716: 7/27,317; 725: 6/29,919) — 40% of the time.
Revision 1 cherry-picked 717-722 and 724 while ignoring 723 (29,303) and 725.
The waste is real but intermittent, which lowers this to P2. Separately, 25,000
is structurally wrong for narrative, whose own prompt targets 10,000-15,000.

### F7 (P2) Dead and half-wired code

| Item | State | Action |
|---|---|---|
| `guard_final_turn_length` (`audio_generator.py:67`) | No-op passthrough since v3.53, with commented-out constants above it | Delete function + call |
| `metadata_generator.generate_metadata_from_content` + `generate_metadata_for_script` | Legacy pair, production-dead but mutually referencing (`:434`) | Delete **together** |
| `TopicExtractor` shim (`topic_extractor.py:423`) | Accepts and logs-then-ignores two params | Keep the class, delete the dead params after migrating callers |
| `_run_dedup_pass_with_retry`, `dedup_pass.py`, `scrub_episodes`, `SettingsKeys.Dedup` | Test-only callers | Delete last, after F4's replacement is chosen |
| `script_content_predupe` | Always NULL | Populate per its **documented** meaning (pre-dedup), do not repurpose |

### F8 (P2) CLAUDE.md corrections

*Correction from revision 1 — my F9 was backwards.* CLAUDE.md is **right** that
the anti-AI rules remain duplicated: `dedup_pass.py:151` still carries its own
inline copy and does not import `anti_ai_rules`, and
`tests/test_anti_ai_rules_sync.py:55` only asserts the file contains the string
"contrasted negation". Separately, CLAUDE.md documents a `script_mode` column
on `topics`; the actual column is `use_dialogue_api`.

---

## 3. Work plan

Reordered per the codex review. Deterministic fixes first; nothing that adds an
LLM call to the critical path ships in v4.01.

### Phase A (P0) — Deterministic lead-segment repeat guard

The last-line defense, and the one that would have caught Aug 8 with certainty.

**Sized to the measured repeat, not to the opener.** The adversarial review
showed the Aug 8 duplication runs through turn 4 (verbatim) at 0.780. A
cold-open rewrite would have satisfied a two-turn metric and shipped the same
lead segment. So:

- New `finalize_script()` called **once**, after expansion, on the final draft.
- **Metric, pinned:** `difflib.SequenceMatcher` ratio on normalized text
  (lowercased, audio tags stripped, whitespace collapsed, the welcome/date
  sentence removed since it is a fixed template that inflates every score).
  No embeddings anywhere in the detection path.
- **Window:** the lead segment — first 6 `SPEAKER_` turns for dialogue, first
  ~1,200 chars for narrative (explicitly defined, not inherited from dialogue).
  Score against the same slice of the last 3 digests. Also record the n=2 and
  n=4 scores for shadow analysis.
- **Threshold** 0.45, configurable. Margin is wide at every window: incident
  0.743-0.834, worst retained adjacent pair 0.156.
- **On trip, regenerate the lead rather than repaint it.** One `claude -p` call
  rewrites the whole lead segment with the offending prior segment supplied as
  "we already covered this; do not lead with it, and do not resemble it".
  Then **re-check across the same window**. If the rewrite still trips, fails,
  or introduces a number absent from the rest of the script, keep the original
  and log at ERROR. Shipping a duplicate with a warning beats shipping a
  fabrication silently.
- Shadow-log all three scores for a week before the threshold is trusted.

### Phase B (P0) — Fix all three prompt renderers

- Delete the "Everything provided is NEW material. Cover it all thoroughly."
  assertion from the skill-file dialogue prompt and from the hardcoded
  fallback. It is false whenever dedup fails open.
- Interpolate `repetition_instructions` (and `story_arc_context`, currently
  always empty) into **all three** renderers, so a computed input can never
  again be silently discarded.
- Rewrite the block itself to carry the actual saturated topic names plus a
  constraint: do not open with these, do not re-explain them, cover a genuine
  new development as an update in the body. Keep "cover every episode" — that
  is about depth, and it is not the problem.
- Acceptance is per-renderer: a rendered-prompt test for each of the three.

### Phase C (P0) — Make pre-gen dedup incapable of inventing text

The root-cause fix for the leak channel, done deterministically rather than by
prompt tuning.

- **Output provenance check.** After each dedup call, verify every sentence of
  the output appears in that chunk's input (normalized match). On violation,
  discard the dedup result and keep the original chunk. A generative filter can
  then no longer introduce wording or facts from prior digests, whatever the
  prompt does.
- **Fix N1**: truncate the prior-digest portion only, and always append sibling
  content **after** truncation so same-batch dedup actually runs.
- **Shrink the context**: prior-digest material drops from 200,000 chars of
  verbatim script to the saturated topic list plus each prior digest's lead.
  Smaller leak surface, smaller bill, and Phase C's provenance check makes the
  remaining exposure non-load-bearing.

### Phase D (P1) — Single mandatory finalization path

- Move the structural variety pass into `finalize_script()` so it runs
  **exactly once, on the final draft**. Net variety calls stay at today's one
  per night rather than adding a second (codex's runtime point).
- **Order it after the hard-floor check** (N5), and re-check length after the
  pass, restoring the pre-pass draft if the pass would push it under the floor.
- Make its speaker-label validation mode-aware so it stops silently no-opping
  on narrative.
- **Fix N4**: a dedup-batch exception logs at ERROR and records that the run
  was undefended, rather than warning and proceeding as if nothing happened.
- **Fix N3**: expansion episodes not present in the pre-dedup cache are deduped
  on demand rather than passed through raw.
- Populate `script_content_predupe` with the pre-finalization draft — which is
  genuinely "pre-dedup" under the column's documented meaning, since the
  lead-repeat guard is the dedup step now.
- A behavioral test asserts `create_digest` reaches `finalize_script` after the
  last expansion, so the next optimization cannot silently drop it the way
  v3.48 did.

### Phase E (P2) — Dead code and docs

Per the F7 table and the F8 corrections. `dedup_pass.py` imports
`anti_ai_rules` if it survives; otherwise it goes and CLAUDE.md's warning is
retired with it.

### Explicitly deferred out of v4.01

- **The whole-episode drop/demote LLM verdict** (revision 1's Phase 2). N2
  makes an erroneous drop permanent, and codex's runtime math leaves no budget
  for nine sequential verdict calls under a 300s-per-episode ceiling against a
  7200s cron cap already at 86%. Revisit with a global deadline, a structured
  schema, and a no-permanent-`digested` rule once Phase C's provenance data
  shows the real drop rate.
- **The story-arc subsystem** (revision 1's Phase 3). Its premise was wrong in
  three separate ways (F3) and it has never affected output. Do not drop the
  tables and do **not** add a second feature flag on top of a database flag
  that is already off. The prerequisite experiment is: turn
  `enable_topic_tracking` on for the topic, run a week, and see whether
  `event_count` actually grows. If it does not, the reconciler's `continue` was
  never the binding constraint and this becomes a removal, not a repair.
  Phase B must therefore **not** take its saturated-topic names from the arc
  path — it reads the evergreen detector's output, which works today.
- **Expansion-loop optimization** (F6). Separate change, separate benchmark.

---

## 4. Test plan

Real data, no mocks, per project standard.

- **Incident regression.** Digests 723/724 and the nine Aug 8 episodes are
  still in the database, but retention will eventually delete them — capture a
  sanitized fixture **now** rather than depending on live row IDs. Assert (a)
  the lead-repeat guard flags the 723/724 pair, and (b) the Google 4% fact is
  absent from a regenerated Aug 8 script, not merely that similarity dropped.
- **Rendered-prompt tests, one per renderer** (skill dialogue, hardcoded
  dialogue, narrative): saturated names present, "everything is new" assertion
  absent.
- **Provenance check**: a dedup output containing a sentence absent from its
  input is rejected and the original retained.
- **N1**: sibling content survives when prior-digest material exceeds the
  truncation budget.
- **Guard boundaries**: the 723/724 pair trips at every window (n=2 0.743,
  n=4 0.780, lead segment); all 14 retained adjacent pairs (≤0.156) pass;
  rewrite failure keeps the original.
- **N5**: a draft just above the hard floor survives finalization rather than
  being pushed under it by the variety pass.
- **N4**: a dedup-batch exception surfaces at ERROR and is visible in the run
  record, not swallowed as a warning.
- **Finalization order**: `finalize_script` runs after the final expansion, on
  both dialogue and narrative, and variety runs exactly once.
- Integration runs against an isolated database or a dry-run mode — the live
  `--phase digest` run mutates state and marks episodes digested.

---

## 5. Risks

- **Guard rewrites the cold open into something worse.** Mitigated by
  re-check-then-revert and by never accepting a rewrite that introduces a
  number absent from the body.
- **Provenance check is too strict** and rejects legitimate dedup output over
  whitespace or punctuation normalization. Mitigated by normalizing before
  comparison and by failing *open to the original transcript*, which is the
  safe direction: worst case is today's behavior minus the dedup benefit.
- **Naming saturated topics anchors the writer** on yesterday's story even
  while forbidding the lead. Watch for it in the first week's output.
- **Runtime.** Phase A adds one deterministic comparison plus a conditional
  ~90s rewrite; Phase D holds variety calls flat; Phase C's smaller context
  reduces dedup tokens. Benchmark against the Aug 8 pool before and after, and
  treat the 7200s cap as the acceptance criterion.
- **Live pipeline.** All changes land and are verified outside the 21:00 PT
  window.

---

## 6. Version

v4.01 in `web_ui_hosted/app/version.ts`, named in the commit message, with
`npm run build` and `npx tsc --noEmit` clean before commit.
