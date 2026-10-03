"""Final-line attribution for script text that Codex actually wrote.

The completion transport (src/utils/claude_quota_fallback.py) can answer a
`claude -p` call with Codex. Paul listens to each digest blind and then reads
the script, so a script whose shipped words include Codex's ends with one
attribution line. It is the LAST line of the published text and nothing else:
every TTS entry point, the metadata prompt, and every reader that hands a
stored script to a model remove it with strip_attribution().

WHAT IS RECORDED. Provenance per accepted stage, not per word. The accepted
draft records who wrote it; each model rewrite that is ACCEPTED into the
shipped script records who wrote it. A rejected, failed, or superseded
attempt records nothing, and a new draft (an expansion iteration) discards
every record from the draft it replaced. The line says "written by Codex"
only when Codex wrote every recorded stage; otherwise it says Codex
contributed and names the stages. It does not estimate how many of Codex's
words survive later rewrites: that cannot be proven from the stages alone.

Provenance comes only from the completion result (`result.provider ==
'codex'`). The line never says why Codex ran: the transport's quota circuit
can route a call to Codex without that call itself having been refused.
"""
import re
from typing import Dict, List, Optional, Tuple

ATTRIBUTION_PREFIX = "Script attribution:"

# Model stages that can contribute shipped words, in pipeline order.
STAGE_LABELS = {
    "draft": "draft",
    "variety": "structural variety rewrite",
    "lead_rewrite": "opening rewrite",
    "length_repair": "length compression",
    "dedup": "dedup rewrite",
    "earlier": "earlier version",
}

Provenance = Tuple[str, Optional[str]]
UNKNOWN = "unknown"


class AuthoredText(str):
    """A completion's text, carrying who produced it.

    Any string operation (strip, slicing, concatenation) returns a plain str,
    so provenance survives only while the text is passed along unchanged.
    """

    provider: str
    model: Optional[str]

    def __new__(cls, text: str, provider: str, model: Optional[str] = None):
        obj = super().__new__(cls, text)
        obj.provider = provider
        obj.model = model
        return obj


def provenance(text) -> Optional[Provenance]:
    """(provider, model) if the text carries provenance, else None."""
    if isinstance(text, AuthoredText):
        return text.provider, text.model
    return None


def carry(text: str, source) -> str:
    """Re-attach source's provenance to text derived from it (e.g. stripped)."""
    p = provenance(source)
    return AuthoredText(text, *p) if p else text


class AuthorshipTracker:
    """Who wrote each accepted stage of the script now being built."""

    def __init__(self):
        self.stages: Dict[str, Tuple[str, Optional[str]]] = {}

    def snapshot(self):
        return dict(self.stages)

    def restore(self, snap) -> None:
        self.stages = dict(snap)

    def start(self, text: str, stage: str = "draft",
              source: Optional[Provenance] = None) -> None:
        """A new base text replaces every earlier record."""
        self.stages = {stage: source if source else (UNKNOWN, None)}

    def apply(self, stage: str, before: str, after: str,
              source: Optional[Provenance]) -> None:
        """An ACCEPTED model rewrite. Call only once its output is kept."""
        self.stages[stage] = source if source else (UNKNOWN, None)

    def finish(self, final_text: str) -> "AuthorshipTracker":
        return self

    def counts(self) -> Dict[str, str]:
        return {stage: who[0] for stage, who in self.stages.items()}


def _join(parts: List[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def _who(provider: str, models: List[str]) -> str:
    if provider == UNKNOWN:
        return "an unrecorded writer"
    if provider == "other":
        return "another writer"
    name = {"codex": "Codex", "claude": "Claude"}.get(provider, provider)
    return f"{name} ({', '.join(models)})" if models else name


def attribution_line(tracker: AuthorshipTracker) -> Optional[str]:
    """The marker for the accepted stages, or None if Codex wrote none."""
    stages = tracker.stages
    codex = [s for s, (p, _) in stages.items() if p == "codex"]
    if not codex:
        return None
    who = _who("codex", sorted({stages[s][1] for s in codex if stages[s][1]}))
    if len(codex) == len(stages):
        return f"{ATTRIBUTION_PREFIX} written by {who}."
    named = [STAGE_LABELS.get(s, s) for s in stages if s in codex]
    others = []
    for provider in dict.fromkeys(p for p, _ in stages.values() if p != "codex"):
        others.append(_who(provider, sorted({m for p, m in stages.values() if p == provider and m})))
    return (f"{ATTRIBUTION_PREFIX} Codex contributed to this script. {who} wrote the "
            f"{_join(named)}; {_join(others)} wrote or revised the rest.")


def final_attribution(script: Optional[str]) -> Optional[str]:
    """The attribution line, if the script's final line is one."""
    if not script:
        return None
    last = script.rstrip().rpartition("\n")[2].strip()
    return last if last.startswith(ATTRIBUTION_PREFIX) else None


def strip_attribution(script: Optional[str]) -> Optional[str]:
    """Remove the attribution line if, and only if, it is the final line."""
    if final_attribution(script) is None:
        return script
    head, sep, _ = script.rstrip().rpartition("\n")
    return head.rstrip() if sep else ""


def append_attribution(script: str, tracker: AuthorshipTracker) -> str:
    """Script with the marker as its last line when Codex words remain.

    The tracker must already be finished against this script's body.
    """
    body = strip_attribution(script)
    line = attribution_line(tracker)
    return body if line is None else f"{body.rstrip()}\n\n{line}"


def tracker_from_published(script: str) -> AuthorshipTracker:
    """Rebuild stage records from a stored script's marker.

    No marker: the earlier text has no recorded Codex stage. "written by
    Codex": Codex wrote all of it. Any other marker: Codex wrote part of it
    and another writer the rest.
    """
    line = final_attribution(script)
    t = AuthorshipTracker()
    if line is None:
        t.stages = {"earlier": (UNKNOWN, None)}
        return t
    m = re.search(r"Codex \(([^),]*)", line)
    model = m.group(1) if m else None
    if re.fullmatch(re.escape(ATTRIBUTION_PREFIX) + r" written by Codex(?: \([^)]*\))?\.", line):
        t.stages = {"earlier": ("codex", model)}
    else:
        t.stages = {"earlier": ("codex", model), "earlier_other": ("other", None)}
    return t


def attribution_after_rewrite(published: str, rewritten: str, stage: str,
                              source: Optional[Provenance]) -> str:
    """Re-attribute a stored script after a later model rewrite of its body
    (the manual dedup CLI). The earlier claim is not carried forward
    blindly: it becomes the "earlier version" stage beside the rewrite."""
    tracker = tracker_from_published(published)
    tracker.apply(stage, strip_attribution(published), rewritten, source)
    return append_attribution(rewritten, tracker)
