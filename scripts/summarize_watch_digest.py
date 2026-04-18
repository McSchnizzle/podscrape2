#!/usr/bin/env python3
"""Summarize a raw watch-themes digest into shape-C (headline + big story + bullets).

Iterate by editing SYNTHESIS_PROMPT below and re-running. Each run writes a
new version-suffixed file so you can diff iterations.

Usage:
  python3 scripts/summarize_watch_digest.py                         # latest raw
  python3 scripts/summarize_watch_digest.py data/watch-digests/2026-04-17-raw.md
"""
from __future__ import annotations

import argparse
import glob
import html
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parent.parent / '.env')

logger = logging.getLogger("summarize_watch_digest")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

WATCH_DIGESTS_DIR = Path("data/watch-digests")
CLAUDE_TIMEOUT_SECONDS = 240


# =============================================================================
# PROMPT — edit this to iterate on the summarization style.
# =============================================================================
SYNTHESIS_PROMPT = """\
You are summarizing one week's worth of podcast excerpts for a single
user-curated theme into a tight, opinionated brief.

INPUT: raw excerpts (direct quotes from podcast transcripts) collected across
multiple episodes, with per-excerpt notes. Many excerpts overlap — the same
story will show up from 3-5 different episodes.

OUTPUT — produce EXACTLY this structure, nothing else:

**[One-sentence headline capturing the dominant story for this theme this week.
No fluff. If the week had multiple comparable stories, pick the one with the
most concrete development/numbers.]**

[A single paragraph, 4-8 sentences, telling the dominant story. Collapse the
overlapping excerpts into one coherent narrative. Preserve load-bearing
numbers (stock %, valuations, specific dollar figures), named companies, and
direct quotes that matter. Cite source episodes inline using parenthetical
italics like "(*Episode Title*)". Do NOT re-list every quote — synthesize.]

**Also this week:**
- [One-liner about a secondary development] — (*Episode Title*)
- [Another secondary development] — (*Episode Title*)
- [etc., 2-4 bullets max]

RULES:
- If fewer than 3 substantive excerpts exist, skip the "Also this week" section.
- If the theme had NO meaningful coverage, return literally: "No significant coverage this week."
- Never invent content not present in the excerpts.
- Never include more than 4 "Also this week" bullets. Drop trivial mentions entirely.
- Do NOT include the theme name in the output — the caller handles headers.
- Do NOT add preamble, explanations, or meta-commentary. Output ONLY the
  formatted markdown.
"""
# =============================================================================


@dataclass
class ThemeBlock:
    name: str
    raw_body: str  # everything under the ## theme heading


def find_latest_raw() -> Path:
    candidates = sorted(WATCH_DIGESTS_DIR.glob("*-raw.md"))
    if not candidates:
        raise SystemExit(f"No *-raw.md files found in {WATCH_DIGESTS_DIR}")
    return candidates[-1]


def parse_themes(raw_markdown: str) -> List[ThemeBlock]:
    """Split a raw watch-digest markdown into per-theme blocks.

    Structure from render_markdown() in run_watch_digest.py:
      # Watch Themes digest — week of YYYY-MM-DD
      ## Theme 1 name
      (body...)
      ## Theme 2 name
      (body...)
    """
    themes: List[ThemeBlock] = []
    current_name = None
    current_body: List[str] = []
    for line in raw_markdown.splitlines():
        if line.startswith("## "):
            if current_name is not None:
                themes.append(ThemeBlock(current_name, "\n".join(current_body).strip()))
            current_name = line[3:].strip()
            current_body = []
        elif current_name is not None:
            current_body.append(line)
    if current_name is not None:
        themes.append(ThemeBlock(current_name, "\n".join(current_body).strip()))
    return themes


def call_claude_p(user_prompt: str, timeout: int = CLAUDE_TIMEOUT_SECONDS) -> str:
    claude_path = os.path.expanduser("~/.local/bin/claude")
    if not os.path.exists(claude_path):
        claude_path = "claude"
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env.pop("ANTHROPIC_API_KEY", None)
    full_prompt = f"{SYNTHESIS_PROMPT}\n\n---\n\n## RAW EXCERPTS TO SUMMARIZE\n\n{user_prompt}"
    result = subprocess.run(
        [claude_path, "-p", "--model", "sonnet", "--effort", "low",
         "--tools", "", "--no-session-persistence", "-"],
        input=full_prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed ({result.returncode}): {result.stderr[:300]}")
    return result.stdout.strip()


def summarize_theme(theme: ThemeBlock) -> str:
    if theme.raw_body.strip().startswith("_No matches") or theme.raw_body.strip().startswith("_Scan error"):
        return "No significant coverage this week."
    logger.info(f"  Summarizing: {theme.name} ({len(theme.raw_body):,} chars raw)")
    try:
        return call_claude_p(f"Theme: {theme.name}\n\n{theme.raw_body}")
    except subprocess.TimeoutExpired:
        return f"_Summarization timeout for {theme.name} — raw excerpts preserved below._\n\n{theme.raw_body[:1000]}"
    except Exception as e:
        return f"_Summarization error for {theme.name}: {e}_\n\n{theme.raw_body[:1000]}"


def render_summarized_markdown(raw_date_header: str, summaries: List[tuple[str, str]]) -> str:
    """Render the new summarized markdown."""
    lines = [f"# {raw_date_header} (summarized)", ""]
    for theme_name, summary in summaries:
        lines.append(f"## {theme_name}")
        lines.append("")
        lines.append(summary)
        lines.append("")
    return "\n".join(lines)


def render_summarized_html(raw_date_header: str, summaries: List[tuple[str, str]]) -> str:
    """Render HTML view of the summarized digest."""
    import markdown as md_lib  # type: ignore
    parts = [
        "<!DOCTYPE html>",
        '<html><head><meta charset="utf-8">',
        f"<title>Watch Themes — {html.escape(raw_date_header)}</title>",
        "<style>body{font-family:-apple-system,system-ui,sans-serif;",
        "max-width:720px;margin:24px auto;padding:0 16px;line-height:1.6;color:#222;}",
        "h1{font-size:24px;margin-bottom:4px}",
        "h2{font-size:18px;margin-top:28px;border-bottom:1px solid #ddd;padding-bottom:4px}",
        "p{margin:12px 0}", "ul{padding-left:24px}", "li{margin:6px 0}",
        "em{color:#555}", "strong{color:#111}",
        "</style></head><body>",
        f'<h1>{html.escape(raw_date_header)}</h1>',
        '<p style="color:#666;font-size:13px">summarized</p>',
    ]
    for theme_name, summary in summaries:
        parts.append(f"<h2>{html.escape(theme_name)}</h2>")
        try:
            parts.append(md_lib.markdown(summary))
        except Exception:
            parts.append(f"<pre>{html.escape(summary)}</pre>")
    parts.append("</body></html>")
    return "\n".join(parts)


def next_version(base_name: str) -> int:
    """Find next version number for a base like '2026-04-17-summary'."""
    pattern = WATCH_DIGESTS_DIR / f"{base_name}-v*.md"
    existing = glob.glob(str(pattern))
    if not existing:
        return 1
    vs = []
    for p in existing:
        m = re.search(r"-v(\d+)\.md$", p)
        if m:
            vs.append(int(m.group(1)))
    return (max(vs) + 1) if vs else 1


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_path", nargs="?", default=None,
                        help="Path to a *-raw.md file; defaults to newest in data/watch-digests/")
    args = parser.parse_args(argv)

    raw_path = Path(args.raw_path) if args.raw_path else find_latest_raw()
    logger.info(f"Reading raw digest: {raw_path}")
    raw_md = raw_path.read_text()

    first_line = raw_md.splitlines()[0] if raw_md else ""
    date_header = first_line.replace("#", "").strip() or raw_path.stem

    themes = parse_themes(raw_md)
    logger.info(f"Parsed {len(themes)} themes")

    summaries: List[tuple[str, str]] = []
    for theme in themes:
        summary = summarize_theme(theme)
        summaries.append((theme.name, summary))

    # Derive base name from raw filename: "2026-04-17-raw" → "2026-04-17-summary"
    base = raw_path.stem.replace("-raw", "-summary")
    v = next_version(base)
    out_md = WATCH_DIGESTS_DIR / f"{base}-v{v}.md"
    out_html = WATCH_DIGESTS_DIR / f"{base}-v{v}.html"

    md_body = render_summarized_markdown(date_header, summaries)
    out_md.write_text(md_body)
    logger.info(f"Wrote {out_md} ({len(md_body):,} chars)")

    try:
        html_body = render_summarized_html(date_header, summaries)
        out_html.write_text(html_body)
        logger.info(f"Wrote {out_html} ({len(html_body):,} chars)")
    except ImportError:
        logger.warning("python-markdown not installed; skipping HTML render. "
                       "pip install markdown for HTML output.")

    print(f"\nSummary: {out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
