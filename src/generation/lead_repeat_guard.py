"""Deterministic guard against opening a digest with the previous day's lead.

WHY THIS EXISTS. On 2026-08-08 the digest opened with the 2026-08-07 cold open
near verbatim -- same hook, same "[surprised] Down four percent" beat, same
"strangest part of this whole thing" close. The two digests shared no source
episodes; the repeated share-price figure appears in none of Aug 8's nine
transcripts, only in Aug 7's *script*. Nothing in the pipeline compared the
finished draft against what had already shipped, so nothing caught it.

DESIGN NOTES, because two of these were review findings:

1. The comparison window is the LEAD SEGMENT, not the cold open. Measured on
   the incident pair, similarity ran 0.834 at one turn, 0.743 at two, 0.820 at
   three, 0.780 at four. Turn 4 was verbatim identical. A guard scoped to the
   first two turns would have been satisfied by a cosmetic rewrite while the
   digest still led with yesterday's story in yesterday's framing.

2. Detection is pure `difflib`. No embeddings, no model call, no network. A
   guard that can fail open under API pressure is not a guard. The only model
   call is the optional repair, and its result must beat the same threshold or
   it is discarded.

3. Normalization strips the welcome/date template ("Welcome to the digest,
   August eighth. I'm ... and we've got nine episodes today"). It is identical
   prose every single night, so leaving it in inflates every score toward the
   threshold and compresses the margin between a normal day and a repeat.

4. The score is the MAX across several window sizes, compared WORD-wise with
   `autojunk=False`. All three of those details were forced by measurement
   against the 14 adjacent pairs in the retained history:

     - Character-wise comparison collapses once the text is normalized.
       `difflib` enables its autojunk heuristic on sequences of 200+ elements,
       treating any element in more than 1% of the sequence as noise -- which,
       for characters, is most of the alphabet. Normalizing makes this WORSE,
       not better: stripping labels, tags and whitespace concentrates the
       character frequencies and pushes more of them over the junk threshold.
       Measured on normalized text, char-wise, autojunk on:

           window   incident   worst normal
           n=2        0.355        0.034
           n=4        0.049        0.020
           n=6        0.034        0.080   <- inverted; a verbatim repeat
                                              scoring BELOW an unrelated pair

       (On RAW text the same comparison holds up -- 0.745/0.137 at n=2 -- so
       the trap is specifically the combination of normalization and
       characters. Both are worth keeping, so the resolution is word tokens.)
       Word tokens plus autojunk=False score the incident 0.821.
     - A single wide window also misses it: at six turns the incident scores
       0.370, under the 0.45 threshold, because the repeat ends after turn
       four and the remaining divergence dilutes it. Taking the max over
       narrow and wide windows catches both a short recycled hook and a long
       recycled segment.

   Measured separation with those settings: incident 0.821, worst normal
   0.187 (the 2026-08-06/07 pair), mean normal 0.104. Both figures are the
   max across windows and the max across argument order -- SequenceMatcher's
   greedy matching is not quite symmetric, and 0.187 is the conservative side
   of a 0.168/0.187 pair.

   IF YOU RE-TUNE THE THRESHOLD, measure with normalize_lead() and not a bare
   tokenizer. Dropping the boilerplate strip moves the worst normal from 0.187
   to 0.278 while moving the incident only 0.821 -> 0.886, i.e. it cuts the
   margin from 4.4x to 3.2x. The nightly welcome template is a constant floor
   under every comparison, and removing it buys more on the negatives than it
   costs on the positive.
"""
from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

# Comparison windows. Dialogue counts speaker turns; narrative counts
# characters because it has no turn structure to count. The score is the max
# across all windows -- see the module docstring for why one window is not
# enough.
LEAD_TURN_WINDOWS = (2, 4, 6)
LEAD_CHAR_WINDOWS = (400, 800, 1200)

# Widest window, used when a caller just wants "the lead segment" as text.
LEAD_TURNS = LEAD_TURN_WINDOWS[-1]
LEAD_CHARS = LEAD_CHAR_WINDOWS[-1]

# Trip threshold. See tests/test_lead_repeat_guard.py for the measured
# separation between normal adjacent digests and the 2026-08-08 incident.
DEFAULT_THRESHOLD = 0.45

# How many recent digests to compare against.
DEFAULT_LOOKBACK = 3

_SPEAKER_RE = re.compile(r"^SPEAKER_\d+:", re.MULTILINE)
_AUDIO_TAG_RE = re.compile(r"\[[^\]]{0,40}\]")
# The nightly welcome template, in the forms the writer actually produces.
_BOILERPLATE_RE = re.compile(
    r"[^.!?]*\b(welcome to the digest|here's the digest|this is the digest)\b[^.!?]*[.!?]",
    re.IGNORECASE,
)
_WS_RE = re.compile(r"\s+")


@dataclass
class LeadRepeatResult:
    """Outcome of comparing a draft's lead against recent digests."""

    score: float
    threshold: float
    tripped: bool
    lead: str
    # Populated only when something scored above zero -- the worst offender.
    matched_digest_id: Optional[int] = None
    matched_digest_date: Optional[str] = None
    matched_lead: Optional[str] = None
    # Diagnostic scores at narrower windows, for shadow analysis.
    scores_by_window: Optional[dict] = None


def extract_lead(script: str, dialogue: bool = True) -> str:
    """Return the lead segment of a script.

    Dialogue: the first LEAD_TURNS speaker turns. Narrative: the first
    LEAD_CHARS characters, trimmed back to a sentence boundary so the slice
    does not end mid-word and skew the ratio.
    """
    if not script:
        return ""

    if dialogue and _SPEAKER_RE.search(script):
        starts = [m.start() for m in _SPEAKER_RE.finditer(script)]
        if len(starts) > LEAD_TURNS:
            return script[: starts[LEAD_TURNS]].strip()
        return script.strip()

    window = script[:LEAD_CHARS]
    if len(script) > LEAD_CHARS:
        cut = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
        if cut > LEAD_CHARS // 2:
            window = window[: cut + 1]
    return window.strip()


def normalize_lead(text: str) -> str:
    """Lowercase, drop speaker labels, audio tags and the nightly boilerplate.

    The boilerplate removal matters: the welcome/date sentence is the same
    every night, so leaving it in raises the floor under every comparison.
    """
    if not text:
        return ""
    out = _SPEAKER_RE.sub(" ", text)
    out = _AUDIO_TAG_RE.sub(" ", out)
    out = _BOILERPLATE_RE.sub(" ", out)
    out = out.lower()
    out = _WS_RE.sub(" ", out)
    return out.strip()


def similarity(a: str, b: str) -> float:
    """Word-wise difflib ratio between two normalized lead segments.

    Word tokens, not characters, and autojunk disabled -- see design note 4 in
    the module docstring. Getting either wrong makes this function report a
    verbatim repeat as less similar than two unrelated digests.
    """
    aw, bw = normalize_lead(a).split(), normalize_lead(b).split()
    if not aw or not bw:
        return 0.0
    return difflib.SequenceMatcher(None, aw, bw, autojunk=False).ratio()


def _lead_at_turns(script: str, turns: int) -> str:
    """The first `turns` speaker turns of a dialogue script."""
    starts = [m.start() for m in _SPEAKER_RE.finditer(script)]
    if len(starts) > turns:
        return script[: starts[turns]]
    return script


def windowed_similarity(a: str, b: str, dialogue: bool = True) -> dict:
    """Similarity at each window size, keyed by window label.

    The caller takes the max. Returning the whole set keeps the per-window
    numbers available for shadow logging and threshold re-tuning.
    """
    if dialogue and _SPEAKER_RE.search(a or ""):
        return {
            f"n{n}": similarity(_lead_at_turns(a, n), _lead_at_turns(b, n))
            for n in LEAD_TURN_WINDOWS
        }
    return {
        f"c{c}": similarity((a or "")[:c], (b or "")[:c]) for c in LEAD_CHAR_WINDOWS
    }


def check_lead_repeat(
    script: str,
    topic: str,
    dialogue: bool = True,
    lookback: int = DEFAULT_LOOKBACK,
    threshold: float = DEFAULT_THRESHOLD,
    exclude_digest_id: Optional[int] = None,
    prior_digests: Optional[List[dict]] = None,
) -> LeadRepeatResult:
    """Compare a draft's lead against the last `lookback` digests for a topic.

    `prior_digests` is injectable so tests can run without a database; when it
    is None the digests are fetched. A fetch failure returns an untripped
    result rather than raising -- the guard must never be the reason a digest
    fails to generate.
    """
    lead = extract_lead(script, dialogue=dialogue)
    if not lead:
        return LeadRepeatResult(score=0.0, threshold=threshold, tripped=False, lead="")

    if prior_digests is None:
        try:
            from src.generation.dedup_pass import _fetch_prior_digests

            prior_digests = _fetch_prior_digests(
                topic=topic, limit=lookback, exclude_digest_id=exclude_digest_id
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(f"Lead-repeat guard: could not fetch prior digests ({exc}); skipping")
            return LeadRepeatResult(score=0.0, threshold=threshold, tripped=False, lead=lead)

    best = LeadRepeatResult(score=0.0, threshold=threshold, tripped=False, lead=lead)
    for prior in prior_digests or []:
        prior_content = prior.get("content", "")
        # Score across every window and take the worst case. A repeat that
        # ends after four turns scores below threshold on a six-turn window
        # alone; see design note 4.
        windows = windowed_similarity(script, prior_content, dialogue=dialogue)
        score = max(windows.values()) if windows else 0.0
        if score > best.score:
            best = LeadRepeatResult(
                score=score,
                threshold=threshold,
                tripped=score >= threshold,
                lead=lead,
                matched_digest_id=prior.get("id"),
                matched_digest_date=prior.get("date"),
                matched_lead=extract_lead(prior_content, dialogue=dialogue),
                scores_by_window={k: round(v, 3) for k, v in windows.items()},
            )

    logger.info(
        f"Lead-repeat guard: score={best.score:.3f} (threshold {threshold}) "
        f"vs digest {best.matched_digest_id or 'n/a'} "
        f"({best.matched_digest_date or 'n/a'}); windows={best.scores_by_window}"
    )
    return best


def build_rewrite_prompt(script: str, result: LeadRepeatResult, dialogue: bool) -> str:
    """Prompt for regenerating a lead segment that repeats a prior digest."""
    fmt = (
        "Keep the SPEAKER_1:/SPEAKER_2: format exactly, one turn per line."
        if dialogue
        else "Keep it single-voice narrative prose with no speaker labels."
    )
    return f"""You are revising the opening of a daily podcast digest.

The opening below repeats the previous digest's opening too closely. Our
audience heard that one yesterday.

## THE OPENING WE ALREADY PUBLISHED (do not resemble this)

{result.matched_lead}

## TODAY'S OPENING (rewrite this)

{result.lead}

## THE REST OF TODAY'S SCRIPT (for context -- do not rewrite, do not repeat)

{script[len(result.lead):len(result.lead) + 6000]}

## RULES

- Lead with a DIFFERENT story from the rest of today's script. Do not open on
  the same story as the published opening above.
- Use only facts that already appear in today's script. Introduce no new
  numbers, names, dates, or claims. This is a re-order and a re-write, not
  new reporting.
- Match the length of today's opening within about 20 percent.
- {fmt}

Output ONLY the replacement opening. No commentary, no headers.
"""


def contains_unsupported_numbers(candidate: str, source: str) -> bool:
    """True if `candidate` introduces a number not present in `source`.

    A rewrite that swaps a duplicate hook for a fabricated statistic is worse
    than the duplicate. Numbers are the cheapest reliable proxy for invented
    facts, and the rewrite prompt forbids new ones, so any new number is a
    contract violation regardless of whether it happens to be true.
    """
    num_re = re.compile(r"\d[\d,.]*")
    source_nums = {n.replace(",", "").rstrip(".") for n in num_re.findall(source)}
    for n in num_re.findall(candidate):
        if n.replace(",", "").rstrip(".") not in source_nums:
            return True
    return False
