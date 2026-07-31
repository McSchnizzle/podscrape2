"""Single source of truth for the anti-AI writing rules.

WHY THIS MODULE EXISTS. The banned-phrase list used to be copy-pasted into four
places -- `.claude/commands/generate-digest.md`, two separate prompts inside
`script_generator.py`, and `dedup_pass.py` -- and they had drifted badly:

    .claude/commands/generate-digest.md   ~20 rules
    script_generator.py (generation)        6 rules
    script_generator.py (variety pass)     ~10 rules
    dedup_pass.py                           6 rules

So a rule added in one place was enforced in one pass and ignored by the rest.
"doing a lot of work" was banned in two of the four; nothing at all was banned
in the dedup pass that wasn't also banned elsewhere.

Everything now derives from the constants below. The markdown skill file cannot
import Python, so it stays a hand-maintained copy -- but
`tests/test_anti_ai_rules_sync.py` asserts it contains every phrase defined
here, which turns silent drift into a failing test.

MEASURED, NOT GUESSED. The rules carrying a `note` were checked against the last
14 days of generated scripts (14 scripts, 327k chars) on 2026-07-31.
"""
from typing import List, Tuple

# (phrase, guidance) -- guidance is shown to the model so it has somewhere to go
# instead of the banned construction.
BANNED_PHRASES: List[Tuple[str, str]] = [
    ("genuinely", 'as an intensifier (use "really," "actually," or nothing)'),
    ("the framing", 'as a noun (use "the argument," "the angle," "the way X put it")'),
    ("deep dive / let's dive into", 'use "let\'s look at," "let\'s get into"'),
    ("break that down for me", 'use "explain that," "how does that work"'),
    ("without further ado", "never"),
    ("mind-blowing / mindblowing", 'use "striking," "remarkable," "wild"'),
    ("I'm intrigued", "react more specifically"),
    ("throughline / through-line", 'use "the connection," "what ties this together"'),
    ("That's a [adjective] [noun]", "as a standalone summary sentence; rewrite as a natural reaction"),
    ("connect the threads / connecting the threads", "find a different way to synthesize each episode"),
    ("what surprised you", "as a formulaic question"),
    ("both things can be true (simultaneously)", "just present both things"),
    ("doing a lot of work (in that sentence)", "AI-generated construction"),
    ("I want to push back on that / I'd push back", "manufactured disagreement"),
    ("I honestly don't know / I haven't figured out what I think", "performed uncertainty"),
]

# Phrases allowed but rationed, as (phrase, max_per_script, guidance).
CAPPED_PHRASES: List[Tuple[str, int, str]] = [
    ("worth [verb]ing", 1, 'editorial filler: "worth noting," "worth sitting with," "worth watching," "worth flagging"'),
    ("specific / specifically", 3, "authenticity-signaling"),
    ("the harness", 1, "as a recurring metaphor"),
    ("Now —", 2, "as a topic transition; vary how you move between topics"),
]

# CONTRASTED NEGATION -- broadened 2026-07-31, and this is the important one.
#
# The rule used to read: '"Not just X, it's Y" construction: MAX 1 per script.'
# Measured against 14 days of output, that exact construction appeared ZERO
# times -- while the same rhetorical move, phrased differently, appeared 31
# times across 14 scripts (2.2 per script), with 10 of 14 scripts over the cap:
#
#     "isn't a bug, it's a feature"
#     "isn't winning because the chip is magical, it's winning because ..."
#     "isn't whose chip is faster today, it's whose software stack catches up"
#     "That's not a polish problem, that's a 'does this model understand ...'"
#     "That's not an improvement, it's a different model class entirely"
#
# The model was obeying the letter of the rule and routing around it with
# synonyms. A ban that names one surface form teaches avoidance of that form,
# not of the habit. So the rule now describes the SHAPE and lists the variants.
CONTRASTED_NEGATION_RULE = (
    "**Contrasted negation: MAX 1 per script.** The 'it's not X, it's Y' move in "
    "ALL its forms -- \"not just X, it's Y\", \"isn't X, it's Y\", \"that's not X, "
    "that's Y\", \"isn't A because B, it's C because D\", \"not a X, a whole Y\". "
    "This is the single most overused AI rhetorical pattern and it is currently "
    "the most frequent one in this show's scripts. Naming one variant does not "
    "help: state the point directly instead of staging a correction. Write \"the "
    "bottleneck is the software stack\" rather than \"it isn't the chip, it's the "
    "software stack.\""
)

STRUCTURAL_RULES: List[str] = [
    "**Em dashes: MAX 15 per script.** Use commas, parentheses, colons, semicolons, and periods instead. Vary your punctuation.",
    "**Triads: Avoid defaulting to exactly 3 items** in comma-separated lists. Use 2, or 4, or 5. Three is the AI default.",
    "**Turn length asymmetry: REQUIRED.** Speaker turns should vary wildly. Never let both speakers consistently take equal-length turns. Some turns are 1 sentence. Some are 5-6.",
    '**Contractions: ALWAYS.** Use "isn\'t" not "is not," "can\'t" not "cannot," "don\'t" not "do not." These are people talking.',
    CONTRASTED_NEGATION_RULE,
]


def banned_phrase_lines() -> List[str]:
    """Markdown bullets for the full banned list, including capped phrases."""
    out = [f'- "{p}" — {g}' for p, g in BANNED_PHRASES]
    out += [f'- "{p}" — {g} — MAX {n} per script' for p, n, g in CAPPED_PHRASES]
    return out


def compact_banned_list() -> str:
    """One-line form for prompts that cannot afford the full block.

    Deliberately includes the contrasted-negation shape: it was absent from
    every short copy of this list, which is precisely why it survived.
    """
    phrases = [
        '"genuinely" (as intensifier)', '"the framing"', '"throughline"',
        '"connect the threads"', '"what surprised you"', '"deep dive"',
        '"break that down"', '"worth noting"', '"both things can be true"',
        '"doing a lot of work"', '"I want to push back"',
        '"I honestly don\'t know"',
    ]
    return (
        "NEVER use these phrases: " + ", ".join(phrases) + ". "
        "NEVER use contrasted negation in any form (\"it's not X, it's Y\", "
        "\"isn't X, it's Y\", \"that's not X, that's Y\") -- state the point "
        "directly instead of staging a correction."
    )


def full_rules_block() -> str:
    """The complete rules section, for prompts that can carry it."""
    parts = ["Banned words and phrases (never use in scripts):"]
    parts += banned_phrase_lines()
    parts.append("")
    parts.append("Structural rules:")
    parts += [f"- {r}" for r in STRUCTURAL_RULES]
    return "\n".join(parts)


def all_banned_substrings() -> List[str]:
    """Lowercased fragments a sync test can look for in the markdown skill file.

    Kept short and distinctive so the check survives rewording of the guidance
    text around each phrase.
    """
    frags = [
        "genuinely", "the framing", "deep dive", "break that down",
        "without further ado", "mind-blowing", "i'm intrigued", "throughline",
        "connect the threads", "what surprised you", "both things can be true",
        "doing a lot of work", "push back", "i honestly don't know",
        "worth", "specific", "the harness", "contrasted negation",
    ]
    return frags
