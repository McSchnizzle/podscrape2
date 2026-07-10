"""Shared Harold UI email shell + components for the Watch Themes digest.

House design system: Harold UI, "Warm Cream / Forest", LIGHT theme only.
This is an email -- it always renders on a light background regardless of
the recipient's mail client theme, so no dark-mode variant is attempted
(per ~/.claude/skills/design/systems/harold-ui.md).

Email clients strip <style> blocks and external stylesheets (Gmail in
particular), so every rule below is inlined as a `style="..."` literal on
each element rather than referencing a stylesheet. Every literal is a copy
of a value from ~/.claude/design/tokens.css -- see PROVENANCE_COMMENT
(embedded in the rendered output) for the token name each one maps back to.

Two callers share this module so the SAME rendered HTML goes to both
delivery channels (Graph email + Harold dashboard POST):
  - scripts/run_watch_digest.py::render_html            (raw excerpts)
  - scripts/summarize_watch_digest.py::render_summarized_html (shape-C, default)
"""
from __future__ import annotations

import html as _html
import re

# ---------------------------------------------------------------------------
# Token literals -- source: ~/.claude/design/tokens.css (LIGHT theme block)
# ---------------------------------------------------------------------------
BG = "#f3efe7"              # --bg
SURFACE_1 = "#ffffff"       # --surface-1
SURFACE_2 = "#faf7f0"       # --surface-2
BORDER = "#e3ddcf"          # --border
BORDER_STRONG = "#cdc5b3"   # --border-strong
TEXT = "#15201c"            # --text
TEXT_MUTED = "#3a4641"      # --text-muted
TEXT_SUBTLE = "#6b756f"     # --text-subtle
ACCENT = "#1f4d40"          # --accent

FONT_SERIF = "'Source Serif 4', Georgia, 'Times New Roman', serif"           # --font-serif
FONT_SANS = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"  # --font-sans

T_H1 = f"font:600 32px/1.15 {FONT_SERIF}; color:{TEXT}; margin:0;"           # --t-h1
T_H2 = f"font:600 24px/1.2 {FONT_SERIF}; color:{TEXT}; margin:0;"            # --t-h2
T_H3 = f"font:600 18px/1.3 {FONT_SANS}; color:{TEXT}; margin:0;"             # --t-h3
T_BODY = f"font:400 15px/1.55 {FONT_SANS}; color:{TEXT}; margin:0;"          # --t-body
T_SMALL = f"font:400 13px/1.5 {FONT_SANS}; color:{TEXT_MUTED}; margin:0;"    # --t-small
T_MICRO = (f"font:600 11px/1.2 {FONT_SANS}; color:{TEXT_SUBTLE}; margin:0; "
           f"text-transform:uppercase; letter-spacing:0.06em;")              # --t-micro

RADIUS = "12px"       # --radius
RADIUS_LG = "16px"    # --radius-lg
SPACE_4 = "16px"      # --space-4
SPACE_5 = "24px"      # --space-5
SPACE_6 = "32px"      # --space-6
SHADOW_MD = "0 14px 50px -18px rgba(21,32,28,0.18), 0 2px 8px -2px rgba(21,32,28,0.04)"  # --shadow-md

PROVENANCE_COMMENT = f"""<!--
  TOKEN PROVENANCE -- Harold UI, Warm Cream / Forest (LIGHT theme only).
  Source: ~/.claude/design/tokens.css. Email clients strip <style> blocks
  and external CSS, so every value in this document is inlined as a
  literal; this comment is the audit trail back to the semantic token name.

  --bg             {BG}  outer page background
  --surface-1      {SURFACE_1}  card background
  --surface-2      {SURFACE_2}  nested / highlight background (callouts, matches)
  --border         {BORDER}  card border, section dividers
  --border-strong  {BORDER_STRONG}  reserved (not used in email; kept for parity)
  --text           {TEXT}  primary text
  --text-muted     {TEXT_MUTED}  secondary text, citations
  --text-subtle    {TEXT_SUBTLE}  metadata, no-match lines
  --accent         {ACCENT}  forest green -- theme headings, callout stripe
  --font-serif     {FONT_SERIF}
  --font-sans      {FONT_SANS}
  --t-h1  600 32px/1.15 serif  -> masthead
  --t-h2  600 24px/1.2  serif  -> theme heading
  --t-h3  600 18px/1.3  sans   -> headline / callout text
  --t-body   400 15px/1.55 sans  -> body copy
  --t-small  400 13px/1.5  sans  -> citations, bullets, meta
  --t-micro  600 11px/1.2  sans  -> eyebrow label (uppercase, tracked)
  --space-4/5/6  {SPACE_4} / {SPACE_5} / {SPACE_6}  -> padding and section gaps
  --radius/-lg   {RADIUS} / {RADIUS_LG}  -> corners
  --shadow-md    card elevation
-->"""


def inline_md(text: str) -> str:
    """Escape text then apply minimal inline markdown: **bold**, *italic*."""
    escaped = _html.escape(text)
    escaped = re.sub(r'\*\*(.+?)\*\*', f'<strong style="color:{TEXT};">\\1</strong>', escaped)
    escaped = re.sub(r'\*(.+?)\*', f'<em style="color:{TEXT_MUTED}; font-style:italic;">\\1</em>', escaped)
    return escaped


def render_shell(*, eyebrow: str, masthead: str, subtitle: str, body_html: str,
                  footer_note: str) -> str:
    """Wrap theme-section HTML in the Harold UI email shell.

    Table-based single-column layout (max 680px) for email-client
    compatibility -- Outlook's Word rendering engine ignores flexbox and
    most modern CSS, but reliably supports nested tables.
    """
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_html.escape(masthead)} — {_html.escape(eyebrow)}</title>
</head>
<body style="margin:0; padding:0; background:{BG};">
{PROVENANCE_COMMENT}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{BG};">
<tr><td align="center" style="padding:{SPACE_6} {SPACE_4};">
<table role="presentation" width="680" cellpadding="0" cellspacing="0" border="0"
       style="max-width:680px; width:100%; background:{SURFACE_1}; border:1px solid {BORDER};
              border-radius:{RADIUS_LG}; box-shadow:{SHADOW_MD};">
<tr><td style="padding:{SPACE_6} {SPACE_6} {SPACE_5};">
  <div style="{T_MICRO}">{_html.escape(eyebrow)}</div>
  <h1 style="{T_H1} margin-top:6px;">{_html.escape(masthead)}</h1>
  <div style="{T_SMALL} color:{TEXT_SUBTLE}; margin-top:6px;">{_html.escape(subtitle)}</div>
</td></tr>
<tr><td style="padding:0 {SPACE_6};"><div style="border-top:1px solid {BORDER}; line-height:1px; font-size:1px;">&nbsp;</div></td></tr>
<tr><td style="padding:{SPACE_5} {SPACE_6} {SPACE_6};">
{body_html}
</td></tr>
<tr><td style="padding:0 {SPACE_6} {SPACE_6};">
  <div style="border-top:1px solid {BORDER}; padding-top:{SPACE_4};">
    <span style="{T_MICRO}">{_html.escape(footer_note)}</span>
  </div>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def render_no_match_line(name: str, detail: str = "no coverage this week") -> str:
    """Compact single muted line for a theme with nothing to report.

    Deliberately NOT a full section -- per house quality bar, empty state
    should be quiet, not a loud box with the same visual weight as a
    matched theme.
    """
    return (
        f'<div style="{T_SMALL} color:{TEXT_SUBTLE}; font-style:italic; '
        f'padding:8px 0; border-bottom:1px solid {BORDER};">'
        f'{_html.escape(name)} — {_html.escape(detail)}</div>'
    )


def render_theme_card_summary(name: str, headline: str, body_paragraphs: list[str],
                               bullets: list[str]) -> str:
    """Render one theme's shape-C summary (headline + narrative + bullets)."""
    parts = [
        f'<h2 style="{T_H2} border-bottom:2px solid {ACCENT}; padding-bottom:8px; '
        f'margin-bottom:{SPACE_4};">{_html.escape(name)}</h2>'
    ]
    if headline:
        parts.append(
            f'<div style="background:{SURFACE_2}; border-left:4px solid {ACCENT}; '
            f'border-radius:0 {RADIUS} {RADIUS} 0; padding:{SPACE_4}; margin:0 0 {SPACE_4};">'
            f'<p style="{T_H3}">{inline_md(headline)}</p></div>'
        )
    for p in body_paragraphs:
        parts.append(f'<p style="{T_BODY} margin:0 0 {SPACE_4};">{inline_md(p)}</p>')
    if bullets:
        items = "".join(
            f'<li style="{T_SMALL} margin-bottom:8px; padding-left:4px;">{inline_md(b)}</li>'
            for b in bullets
        )
        parts.append(
            f'<div style="{T_MICRO} color:{ACCENT}; margin:{SPACE_4} 0 8px;">Also this week</div>'
            f'<ul style="margin:0; padding-left:20px;">{items}</ul>'
        )
    return (
        f'<div style="margin-bottom:{SPACE_5}; padding-bottom:{SPACE_5}; '
        f'border-bottom:1px solid {BORDER};">' + "".join(parts) + '</div>'
    )


def render_theme_card_raw(name: str, matches: list) -> str:
    """Render one theme's raw excerpt matches (dry-run / --no-summarize path).

    `matches` is duck-typed: objects with .excerpt, .relevance_note,
    .episode_title, .episode_date (ThemeMatch dataclass instances in
    run_watch_digest.py).
    """
    parts = [
        f'<h2 style="{T_H2} border-bottom:2px solid {ACCENT}; padding-bottom:8px; '
        f'margin-bottom:{SPACE_4};">{_html.escape(name)}</h2>'
    ]
    for m in matches:
        note_html = (
            f'<p style="{T_SMALL} margin:8px 0 0;">{_html.escape(m.relevance_note)}</p>'
            if getattr(m, "relevance_note", "") else ""
        )
        parts.append(
            f'<div style="background:{SURFACE_2}; border-left:4px solid {ACCENT}; '
            f'border-radius:0 {RADIUS} {RADIUS} 0; padding:{SPACE_4}; margin-bottom:12px;">'
            f'<p style="{T_BODY} font-style:italic; margin:0;">'
            f'&ldquo;{_html.escape(m.excerpt)}&rdquo;</p>'
            f'{note_html}'
            f'<div style="{T_SMALL} color:{TEXT_SUBTLE}; margin-top:8px;">'
            f'— {_html.escape(m.episode_title)} ({m.episode_date.isoformat()})</div>'
            f'</div>'
        )
    return (
        f'<div style="margin-bottom:{SPACE_5}; padding-bottom:{SPACE_5}; '
        f'border-bottom:1px solid {BORDER};">' + "".join(parts) + '</div>'
    )
