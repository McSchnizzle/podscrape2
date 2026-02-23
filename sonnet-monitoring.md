# Sonnet Digest Script Monitoring

Tracking script quality, length, and cost-efficiency as we evaluate Claude Sonnet for digest generation.

## Context
- Switched from GPT to Claude Sonnet for script generation
- Sonnet voice quality is excellent: natural dialogue, good explanations, conversational feel
- Main concern: scripts are longer than needed, and every TTS minute costs money
- Goal: find the right length/quality tradeoff without losing the Sonnet voice

---

## Episode 546 - "Agentic AI Deep Dive" (Feb 22, 2026)

**Stats**: 53,517 chars | ~53k words reported | 4,244s (70 min) audio | 4 source episodes

### Paul's Observations (Feb 23)
- Around the 60% mark, the conversation transitions into technical deep dive, discussion, and key takeaways
- Those sections are not as valuable and are often redundant with what was already covered
- Not entirely without value - e.g. the additional discussion about Indie Dev Dan's browser testing episode added something new
- But overall the final ~40% could be significantly condensed
- **Core concern**: every minute costs real TTS money, need to be thoughtful about length

### Claude's Structural Analysis

**Script structure breakdown:**

| Section | Lines | ~% of Script | Value Assessment |
|---------|-------|-------------|-----------------|
| Intro/setup | 1-5 | 2% | Essential |
| Ep 1: Indie Dev Dan 4-layer architecture | 6-52 | 17% | Strong - detailed, engaging |
| Ep 2: Codebase understanding prompts | 53-75 | 8% | Good - concise, adds value |
| Ep 3: Accounting agent | 77-103 | 9% | Good - practical, well-paced |
| Ep 4: Plumbers vs programmers | 105-159 | 20% | Good - macro framing, data-rich |
| First synthesis ("tie together") | 161-171 | 4% | **High value** - the "so what" moment |
| Technical deep dive | 173-223 | 18% | **LOW VALUE - mostly redundant** |
| Actionable takeaways | 225-247 | 8% | Mixed - some good, too long |
| Cross-episode connections | 249-263 | 5% | **Redundant** with first synthesis |
| Things to watch + wrap-up | 265-279 | 5% | Decent, could be tighter |

**The ~60% inflection point Paul identified maps to line ~167 (the first synthesis).**

### Specific Redundancy Examples

1. **CLI vs MCP debate** (lines 175-179): Already thoroughly covered in Ep 1 discussion (lines 14-16). The deep dive section re-explains the same point almost verbatim.

2. **Parallel execution / Playwright** (lines 181-187): Already covered at lines 31-35. The deep dive adds minor detail about named sessions but mostly restates.

3. **Skill update pattern** (lines 197-203): Already well-explained at lines 93-95. The deep dive just rewords it.

4. **Gen Z survey data** (lines 207-215): Already presented in full during Ep 4 coverage (lines 139-147). The deep dive re-cites the same numbers.

5. **Cross-episode connections** (lines 249-263): The first synthesis at lines 161-171 already does this well. This second pass is almost entirely redundant.

### What the "second pass" should cut or condense

**Definitely cut:**
- Technical deep dive section (lines 173-223) - ~18% of script, mostly rehash
- Second cross-episode connections (lines 249-263) - 5% of script, redundant with first synthesis

**Condense:**
- Actionable takeaways (lines 225-247) - could be 3-4 lines instead of 12
- Things to watch (lines 265-275) - could be integrated into the sign-off

**Keep as-is:**
- All four episode coverage sections (lines 1-159) - this is the core value
- First synthesis (lines 161-171) - natural, concise, earns its place
- Sign-off (lines 277-279)

### Estimated savings
- Current: 53,517 chars → ~70 min audio
- If redundant sections cut: ~35,000-38,000 chars → ~45-50 min audio
- **Potential savings: ~20-25 min of TTS per episode (~30% cost reduction)**

---

## Root Cause Analysis: Production Prompt vs Test Prompt

### The critical finding

**Ep 543 (Sonnet's first test, simplified prompt) does NOT have the redundancy problem.** The production episodes 545-546 do. This means the problem is primarily prompt-driven, not model-driven.

### Episode 543 - "Pentagon vs Anthropic & AI Chaos" (Sonnet test, Feb 20)

**Stats**: 32,707 chars | 2,609s (43 min) audio | 4 source episodes | Simplified test prompt

| Section | Lines | % | Assessment |
|---------|-------|---|------------|
| Episode coverage (all stories) | 15-141 | ~77% | Strong, dense |
| Throughline synthesis | 143-151 | ~5% | Brief, names "governance gap" frame — earns its place |
| Actionable takeaways | 153-165 | ~8% | **Actually good** — audience-specific, concrete, additive |
| Wrap-up + sign-off | 167-173 | ~4% | Tight |

**Key differences from 545/546:**
- Takeaways are targeted to 5 specific audiences ("if you work in education", "if you're building autonomous agents", "if you're in consumer electronics") with concrete action items — NOT restating what was already said
- No "technical deep dive" rehash section
- No second synthesis/connections pass
- No repeated data points or statistics
- Well-proportioned: 77% coverage, 17% synthesis+takeaways+close

**543 is what a good Sonnet digest looks like.** The voice is natural, the coverage is thorough, and the wrap-up adds value rather than repeating it.

### What changed between 543 (good) and 545-546 (bloated)?

The production prompt (`src/generation/script_generator.py`, line 918-1001) adds several components not present in the simplified test:

**1. Story arc context** (`_get_recent_story_arc_context`, line 902-906)
- Injects hot/developing/emerging arcs with events, categories, source counts
- Can add thousands of chars to the system prompt
- Gives Sonnet more material to synthesize and cross-reference

**2. Repetition avoidance instructions** (`_build_repetition_avoidance_instructions`, line 908-912)
- Lists recently-covered arcs with strict rules
- Ironically, drawing attention to "don't repeat these" may cause Sonnet to re-engage with them

**3. Topic instructions** (`instructions_md` field, 6,714 chars for AI and Technology)
- **This is likely the primary culprit**
- The instructions explicitly request sections like: "Key Highlights", "Detailed Analysis", "Discussion", "Key Takeaways"
- Sonnet faithfully produces ALL of these sections — first during natural episode coverage, then AGAIN as dedicated post-coverage sections
- The instructions were written for GPT models that produced 20-25k chars; Sonnet interprets them more expansively

**4. Larger input context overall**
- Test: ~47k input tokens (already higher than other models)
- Production: even larger with story arcs + repetition avoidance + full ad-filtered transcripts
- More input → more material for Sonnet to synthesize → longer output

### The production system prompt structure (line 918-971)

```
System prompt includes:
├── Format instructions (SPEAKER_1/SPEAKER_2 rules, audio tags)     ~2k chars
├── Character roles (speaker names from voice_config)                ~200 chars
├── Topic instructions (from instructions_md in database)            ~6.7k chars  ← PROBLEM
├── Story arc context (dynamic, from database)                       ~variable
├── Repetition avoidance (dynamic, recently covered arcs)            ~variable
├── Story arc grounding rules                                        ~300 chars
├── Target: "25,000-30,000 characters"                               ~200 chars
└── Date/topic/episode count                                         ~100 chars
```

The character target (25-30k) is stated but not enforced. The code warns at line 1016 when output exceeds 30k but doesn't truncate or reject.

### Why 543 worked and 545-546 didn't

| Factor | Ep 543 (test) | Ep 545-546 (production) |
|--------|---------------|------------------------|
| Topic instructions | Simplified/absent | Full 6,714 chars requesting multiple sections |
| Story arc context | None | Yes - additional synthesizable material |
| Repetition avoidance | None | Yes - may paradoxically encourage re-engagement |
| Character target | Likely similar | "25,000-30,000 characters" (ignored) |
| Result | 33k chars, well-structured | 49-53k chars, redundant tail |

### Revised diagnosis

**The problem is not "Sonnet is verbose." The problem is "the production prompt tells Sonnet to produce redundant sections, and Sonnet is too good at following instructions."**

The topic instructions were designed for GPT models that naturally produce shorter output. Sonnet interprets the same instructions more literally and expansively:
- GPT sees "Key Takeaways" and writes 3-4 bullet points
- Sonnet sees "Key Takeaways" and writes a full 12-line dialogue section restating every major point

The fix should target the instructions, not the model.

---

## Model Comparison Reference (Feb 20, 2026)

From `data/model_comparison/comparison_report.md`:

| Model | Output chars | Cost | Notes |
|-------|-------------|------|-------|
| Claude Opus 4.5 | 19,190 | $0.80 | Only model in target range |
| GPT-5.2 (thinking) | 21,357 | $0.11 | Slightly over |
| GPT-5.2 (chat) | 23,330 | $0.10 | Over by 17% |
| Claude Haiku 4.5 | 27,325 | $0.05 | Over by 37% |
| **Claude Sonnet 4.6** | **32,707** | **$0.25** | **Over by 64%** |

In production with full prompts: Sonnet now produces 49-53k (100-120% over target).

**The prompt is the multiplier**: Sonnet went from 64% over (test) to 100-120% over (production) — the additional prompt material roughly doubled the overshoot.

## Model Comparison Reference (Feb 20, 2026)

From `data/model_comparison/comparison_report.md`:

| Model | Output chars | Cost | Notes |
|-------|-------------|------|-------|
| Claude Opus 4.5 | 19,190 | $0.80 | Only model in target range |
| GPT-5.2 (thinking) | 21,357 | $0.11 | Slightly over |
| GPT-5.2 (chat) | 23,330 | $0.10 | Over by 17% |
| Claude Haiku 4.5 | 27,325 | $0.05 | Over by 37% |
| **Claude Sonnet 4.6** | **32,707** | **$0.25** | **Over by 64%** |

In production with full prompts: Sonnet now produces 49-53k (100-120% over target).

---

## Approach Options for Reducing Length

### Option A: Revise topic instructions (instructions_md) — HIGHEST PRIORITY
- The `instructions_md` for "AI and Technology" (6,714 chars) explicitly requests sections that Sonnet over-produces
- Remove or consolidate the "Discussion" and "Key Takeaways" sections from instructions
- Replace with: "After covering episodes, provide a brief (2-3 exchange) synthesis connecting themes, then close"
- Add explicit anti-redundancy instruction: "Do NOT re-explain topics already covered in episode discussion"
- This is what made ep 543 good — simpler instructions → better proportioned output
- **Risk**: low — the good Sonnet voice comes from episode coverage, not from the instructions structure

### Option B: Enforce character target in the prompt
- Current prompt says "Target 25,000-30,000 characters" — Sonnet ignores this
- Change to: "HARD LIMIT: 28,000-35,000 characters. Scripts exceeding 35,000 characters will be rejected."
- Consider adding: "If approaching the limit, prioritize episode coverage over synthesis sections"
- Target 35k chars → ~45 min audio (Paul's sweet spot of 35-40 min + buffer)

### Option C: Second-pass condensation API call
- Generate full script as-is (Sonnet's natural voice)
- Second API call to identify and cut redundancy, condense takeaways
- Pro: preserves Sonnet's natural generation quality, surgical cuts only
- Con: additional API cost (though much less than TTS savings)
- Better as a safety net than a primary strategy

### Option D: Hybrid (RECOMMENDED)
1. Revise `instructions_md` to remove redundancy-inducing section requests (Option A)
2. Set hard character limit at 35k in the prompt (Option B)
3. If still over 35k after A+B, add a light second-pass trim (Option C)

**Expected outcome**: Based on ep 543 (simplified prompt → 33k, well-structured), revising the instructions alone should bring production output to ~33-38k chars (~43-50 min). Adding a hard limit would cap it at 35k (~45 min). This hits Paul's 35-40 min target.

---

## Episode 545 - "OpenClaw Acquired & Agent AI Surge" (Feb 22, 2026)

**Stats**: 49,628 chars | ~49k words reported | 3,939s (66 min) audio | 4 source episodes

### Claude's Structural Analysis

**Same pattern as ep 546, slightly less severe.**

| Section | Lines | ~% of Script | Value Assessment |
|---------|-------|-------------|-----------------|
| Intro | 1-5 | 2% | Essential |
| OpenClaw acquisition story | 6-41 | 17% | Strong - dramatic, well-paced |
| GitHub trending + agentic file search | 42-91 | 24% | Good - lots of projects, informative |
| Voice input episode | 93-119 | 13% | Good - practical, compelling |
| More GitHub trending projects | 121-155 | 17% | Good - useful project roundup |
| Brief safety synthesis | 157-159 | 1% | Good - concise |
| **"Insights and connections"** | 161-171 | 5% | **Redundant** - restates 4 "patterns" already covered |
| **Actionable takeaways** | 173-189 | 8% | **Mostly redundant** - rehashes episode highlights |
| **Additional reflection (voice/privacy)** | 191-195 | 2% | **Redundant** - voice episode already covered this |
| Wrap-up + sign-off | 197-207 | 5% | Decent, could be tighter |

### Redundancy pattern confirmed

The tail sections (lines 161-195) are ~15% of the script and follow the same formula as ep 546:

1. **"Insights and connections"** (lines 161-171): Identifies 4 "patterns" — generalization thesis, democratization of agentic infra, voice-first shift, openness vs safety. Every one of these was already stated during the episode coverage itself. The "generalization thesis" was covered at line 89-91. The voice shift was covered at lines 117-119. Openness vs safety was covered at lines 17-41.

2. **"Actionable takeaways"** (lines 173-189): Restates: "use generalized tools" (already said), "try voice input" (already said), "take security seriously" (already said), "multi-agent architectures unlock more" (already said), "Anthropic fumbled the community relationship" (already said at lines 27-31).

3. **Voice/privacy reflection** (lines 191-195): Rehashes the local-first privacy point from lines 115-119.

### Key difference from ep 546
- Ep 545 redundancy is ~15% vs ep 546's ~32%
- The episode coverage sections in 545 are denser (more projects to cover), leaving less room for rehash
- But the structural pattern is identical: strong episode coverage → redundant multi-section wrap-up

### Estimated savings
- Current: 49,628 chars → ~66 min audio
- If redundant tail cut: ~42,000 chars → ~55 min audio
- **Potential savings: ~10 min of TTS (~15% cost reduction)**

### Emerging pattern across both episodes

| Metric | Ep 546 | Ep 545 |
|--------|--------|--------|
| Total chars | 53,517 | 49,628 |
| Audio duration | 70 min | 66 min |
| Episode coverage % | ~56% | ~73% |
| Redundant tail % | ~32% | ~15% |
| Redundant tail sections | 4 (deep dive, takeaways, connections, things to watch) | 3 (insights, takeaways, reflection) |
| Estimated saveable time | 20-25 min | ~10 min |

**Observation**: The more source episodes Sonnet has to cover, the less room it has for rehash. Ep 545 covered more GitHub projects so the coverage sections were denser, naturally constraining the tail. But when there's more room (ep 546 with only 4 episodes to cover in depth), Sonnet fills it with redundant synthesis.

This suggests a **character cap** would be the most reliable fix — it forces Sonnet to prioritize coverage over rehash regardless of how many source episodes exist.

---

## Prompt Change Log

### Change #1: Revised `instructions_md` for AI and Technology (Feb 23, 2026)

**Date applied**: 2026-02-23, evening
**First affected episode**: EP 547 (expected 2026-02-24)
**Backup**: `data/instructions_md_backup_20260223.md`

**What changed**: Rewrote the `instructions_md` stored in the `topics` table for "AI and Technology"
- **Before**: 6,714 chars with 6 sections including 8-category "Detailed Analysis", "Insights & Connections", "Cross-References & Context", and "Actionable Takeaways"
- **After**: 3,742 chars with 3 sections: "Episode Coverage" (~80%), "Connecting the Threads" (2-3 exchanges), "What Surprised Us" (2-3 exchanges)

**Sections removed**:
- "Detailed Analysis" (8 sub-categories: AI Models, Research, Industry, Developer Tools, Policy, Culture, Business, Market Impact) — primary redundancy driver, told model to re-analyze everything by category after already covering it as stories
- "Insights & Connections" — replaced with shorter "Connecting the Threads"
- "Cross-References & Context" — folded into episode coverage ("weave cross-references naturally")
- "Actionable Takeaways" — replaced with "What Surprised Us" closer

**Sections added**:
- "What NOT to Do" — explicit anti-patterns (no audience-segmented takeaways, no restating covered data, no generic sign-off platitudes)
- "What Surprised Us" — each host names one genuinely surprising detail, naturally non-redundant
- "Episode Coverage" marked as ~80% of script, with instruction to cover categories organically within stories

**What was NOT changed**:
- Character target in `script_generator.py` still says "Target 25,000-30,000 characters"
- Story arc context injection unchanged
- Repetition avoidance instructions unchanged
- No code changes — instructions_md only

**Expected impact**:
- Output should drop from 49-53k chars (65-70 min) to ~30-38k chars (~40-50 min)
- Redundant tail sections (15-32% of script) should be nearly eliminated
- Episode coverage should increase from 56-73% to ~80% of total script
- "What Surprised Us" closer should feel fresher than formulaic takeaways

**Baseline for comparison (last 5 AI & Technology episodes)**:

| EP | Date | Chars | Duration | Model | Prompt Version |
|----|------|-------|----------|-------|---------------|
| 542 | 2026-02-20 | 22,729 | 30 min | Opus 4.5 (test) | Test prompt (15-20k target) |
| 543 | 2026-02-20 | 32,707 | 43 min | Sonnet 4.6 (test) | Test prompt (15-20k target) |
| 544 | 2026-02-21 | 21,724 | 28 min | GPT (production) | Old instructions (6,714 chars) |
| 545 | 2026-02-22 | 49,370 | 65 min | Sonnet 4.6 (prod) | Old instructions (6,714 chars) |
| 546 | 2026-02-22 | 53,212 | 70 min | Sonnet 4.6 (prod) | Old instructions (6,714 chars) |
| **547** | **2026-02-24** | **TBD** | **TBD** | **Sonnet 4.6 (prod)** | **New instructions (3,742 chars)** |

**Success criteria**:
- EP 547 output < 38,000 chars (< 50 min audio)
- No redundant "Detailed Analysis" or "Actionable Takeaways" sections
- "What Surprised Us" closer present and non-redundant
- Episode coverage quality maintained (the Sonnet voice is the goal to preserve)

**If it doesn't work**:
- If still > 40k: add hard character cap in `script_generator.py` (Option B)
- If quality degrades: check if removal of category headers caused coverage gaps
- If "What Surprised Us" feels forced: consider "one thing to try this week" alternative

---

## Daily Log

### Feb 23, 2026
- Reviewed ep 546 in detail: 32% redundancy in tail sections (deep dive, takeaways, connections, things to watch)
- Reviewed ep 545: same pattern, less severe (15% redundancy)
- Paul's 60% observation maps precisely to the structural inflection point
- **Key breakthrough**: Reviewed ep 543 (Sonnet's first test output, simplified prompt) — NO redundancy problem
  - 543 is well-proportioned: 77% coverage, 17% wrap-up, all additive
  - Takeaways in 543 are audience-specific and concrete, not rehash
  - 543 was 33k chars / 43 min — close to Paul's target of 35-40 min
- **Root cause identified**: The production prompt's `instructions_md` (6,714 chars) explicitly requests sections like "Discussion" and "Key Takeaways" that Sonnet over-produces. GPT treated these as light suggestions; Sonnet treats them as mandates and produces full dialogue sections for each.
- Story arc context and repetition avoidance instructions further inflate the output
- **Diagnosis shift**: Not "Sonnet is verbose" but "the production prompt tells Sonnet to be verbose"
- Revised approach: fix the instructions first (Option A), enforce character limit (Option B), second-pass as safety net (Option C)
- Found full model comparison data in `data/model_comparison/` — mapped all 5 test models to files and DB entries
- Reviewed past month of takeaways (19 episodes, 677 lines): formulaic, repetitive, rarely additive
  - Same phrases appear in nearly every episode ("the winners won't be...", "stay curious, stay critical")
  - GPT takeaways: rigid audience-segmented template, generic week over week
  - Sonnet takeaways: same template when production prompt used, better when test prompt used (ep 543)
- **Applied instructions_md change** (Change #1 above) — first affected episode: EP 547
- Backup saved to `data/instructions_md_backup_20260223.md`
