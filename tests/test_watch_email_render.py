"""Tests for the redesigned Watch Themes email (watch-themes daily emphasis,
Paul 2026-07-10) -- Harold UI, Warm Cream / Forest, light theme, all styles
inlined for email-client compatibility. Covers both renderers that share
src/watch/email_render.py: the default shape-C summary and the raw/
--no-summarize excerpt view.
"""
from __future__ import annotations

from datetime import date

from src.watch import email_render
from scripts.summarize_watch_digest import render_summarized_html, parse_summary_markdown
from scripts.run_watch_digest import render_html, ThemeResult, ThemeMatch


# ---------------------------------------------------------------------------
# Shared shell / inline-style contract
# ---------------------------------------------------------------------------

class TestEmailShellInlineStyles:
    def test_no_style_tag_emitted(self):
        html = email_render.render_shell(
            eyebrow="WEEK OF 2026-07-10", masthead="Watch Themes",
            subtitle="test", body_html="<p>x</p>", footer_note="footer",
        )
        # Only mention of "<style" allowed is inside the provenance HTML
        # comment explaining WHY there's no <style> tag.
        assert html.count("<style") == 1
        assert "Email clients strip <style> blocks" in html

    def test_key_palette_literals_present(self):
        html = email_render.render_shell(
            eyebrow="e", masthead="m", subtitle="s", body_html="<p>x</p>", footer_note="f",
        )
        assert email_render.BG in html
        assert email_render.SURFACE_1 in html
        assert email_render.ACCENT in html
        assert email_render.TEXT in html
        assert email_render.BORDER in html

    def test_provenance_comment_maps_every_literal_to_a_token_name(self):
        html = email_render.render_shell(
            eyebrow="e", masthead="m", subtitle="s", body_html="<p>x</p>", footer_note="f",
        )
        assert "TOKEN PROVENANCE" in html
        for token_name in ("--bg", "--surface-1", "--accent", "--text", "--border",
                           "--font-serif", "--font-sans", "--t-h1", "--t-h2", "--t-body"):
            assert token_name in html

    def test_table_based_layout_max_width_680(self):
        html = email_render.render_shell(
            eyebrow="e", masthead="m", subtitle="s", body_html="<p>x</p>", footer_note="f",
        )
        assert 'width="680"' in html
        assert "max-width:680px" in html

    def test_masthead_and_eyebrow_escaped_and_present(self):
        html = email_render.render_shell(
            eyebrow="WEEK OF 2026-07-10", masthead="Watch Themes",
            subtitle="sub<script>", body_html="<p>x</p>", footer_note="f",
        )
        assert "WEEK OF 2026-07-10" in html
        assert "Watch Themes" in html
        assert "<script>" not in html  # subtitle must be escaped


# ---------------------------------------------------------------------------
# No-match rendering: compact muted line, not a loud section
# ---------------------------------------------------------------------------

class TestNoMatchLine:
    def test_no_match_line_is_compact_single_element(self):
        line = email_render.render_no_match_line("Some Theme")
        assert line.count("<div") == 1  # one element, not a card/section
        assert "<h2" not in line  # no heading -- not a full section
        assert "no coverage this week" in line
        assert email_render.TEXT_SUBTLE in line  # muted color, not full-strength text

    def test_no_match_line_custom_detail(self):
        line = email_render.render_no_match_line("Theme X", detail="scan error: boom")
        assert "scan error: boom" in line


# ---------------------------------------------------------------------------
# Shape-C summary parsing + rendering (default delivery path)
# ---------------------------------------------------------------------------

class TestParseSummaryMarkdown:
    def test_no_coverage_literal(self):
        parsed = parse_summary_markdown("No significant coverage this week.")
        assert parsed["no_match"] is True

    def test_summarization_error_fallback(self):
        parsed = parse_summary_markdown("_Summarization error for X: boom_\n\nraw excerpts")
        assert parsed["no_match"] is True

    def test_headline_body_and_bullets_parsed(self):
        summary = (
            "**Allbirds stock surged after AI pivot.**\n\n"
            "The week's sharpest story was Allbirds pivoting to AI "
            "(*Episode A*).\n\n"
            "**Also this week:**\n"
            "- One-liner one — (*Episode B*)\n"
            "- One-liner two — (*Episode C*)\n"
        )
        parsed = parse_summary_markdown(summary)
        assert parsed["no_match"] is False
        assert parsed["headline"] == "Allbirds stock surged after AI pivot."
        assert len(parsed["body_paragraphs"]) == 1
        assert "Allbirds pivoting to AI" in parsed["body_paragraphs"][0]
        assert len(parsed["bullets"]) == 2
        assert parsed["bullets"][0].startswith("One-liner one")

    def test_no_also_this_week_section(self):
        summary = "**Headline.**\n\nJust one paragraph, no bullets."
        parsed = parse_summary_markdown(summary)
        assert parsed["bullets"] == []
        assert parsed["headline"] == "Headline."


class TestRenderSummarizedHtml:
    def _sample_summaries(self):
        return [
            (
                "AI impact on public company stock prices",
                "**Allbirds stock surged after AI pivot.**\n\n"
                "The week's sharpest story was Allbirds (*Episode A*).\n\n"
                "**Also this week:**\n- A secondary story — (*Episode B*)\n",
            ),
            (
                "User hatred of Microsoft Copilot",
                "No significant coverage this week.",
            ),
        ]

    def test_matched_theme_gets_full_card(self):
        html = render_summarized_html(
            "Watch Themes digest — week of 2026-07-10 (summarized)",
            self._sample_summaries(),
        )
        assert "AI impact on public company stock prices" in html
        assert "Allbirds stock surged after AI pivot" in html
        assert "A secondary story" in html
        assert "Also this week" in html

    def test_unmatched_theme_collapses_to_muted_line(self):
        html = render_summarized_html(
            "Watch Themes digest — week of 2026-07-10 (summarized)",
            self._sample_summaries(),
        )
        assert "User hatred of Microsoft Copilot — no significant coverage this week" in html

    def test_eyebrow_extracts_week_of_date(self):
        html = render_summarized_html(
            "Watch Themes digest — week of 2026-07-10 (summarized)",
            self._sample_summaries(),
        )
        assert "WEEK OF 2026-07-10" in html

    def test_inline_italic_citation_markdown_converted(self):
        html = render_summarized_html(
            "week of 2026-07-10", self._sample_summaries(),
        )
        assert "<em" in html
        assert "(*Episode A*)" not in html

    def test_inline_bold_markdown_converted_in_body_text(self):
        summaries = [(
            "Theme",
            "**Headline.**\n\nBody text with **a bolded phrase** inside it (*Cited Episode*).\n",
        )]
        html = render_summarized_html("week of 2026-07-10", summaries)
        assert "<strong" in html
        assert "a bolded phrase" in html
        assert "**a bolded phrase**" not in html

    def test_no_style_tag_in_full_output(self):
        html = render_summarized_html("week of 2026-07-10", self._sample_summaries())
        assert html.count("<style") == 1  # provenance comment mention only


# ---------------------------------------------------------------------------
# Raw excerpt rendering (dry-run / --no-summarize path)
# ---------------------------------------------------------------------------

class TestRenderHtmlRaw:
    def test_matched_theme_renders_excerpt_cards(self):
        results = [
            ThemeResult(
                theme_id=1, theme_name="AI impact on politics and elections",
                theme_description="d", episodes_scanned=3,
                matches=[
                    ThemeMatch(
                        episode_id=10, episode_title="Episode X",
                        episode_date=date(2026, 7, 8),
                        excerpt="AI money floods into campaigns",
                        relevance_note="matches political spending angle",
                    ),
                ],
            ),
        ]
        html = render_html(date(2026, 7, 10), results)
        assert "AI impact on politics and elections" in html
        assert "AI money floods into campaigns" in html
        assert "matches political spending angle" in html
        assert "Episode X" in html
        assert "2026-07-08" in html

    def test_no_match_theme_collapses_to_muted_line(self):
        results = [
            ThemeResult(
                theme_id=2, theme_name="User hatred of Microsoft Copilot",
                theme_description="d", episodes_scanned=5, matches=[],
            ),
        ]
        html = render_html(date(2026, 7, 10), results)
        assert "User hatred of Microsoft Copilot" in html
        assert "no matches this week" in html
        assert "scanned 5 episodes" in html

    def test_error_theme_collapses_to_muted_line(self):
        results = [
            ThemeResult(
                theme_id=3, theme_name="Errored theme",
                theme_description="d", episodes_scanned=0, matches=[],
                error="claude -p timed out",
            ),
        ]
        html = render_html(date(2026, 7, 10), results)
        assert "scan error: claude -p timed out" in html

    def test_subtitle_reports_totals(self):
        results = [
            ThemeResult(theme_id=1, theme_name="A", theme_description="d",
                       episodes_scanned=1, matches=[
                           ThemeMatch(episode_id=1, episode_title="E",
                                     episode_date=date(2026, 7, 8),
                                     excerpt="x", relevance_note=""),
                       ]),
            ThemeResult(theme_id=2, theme_name="B", theme_description="d",
                       episodes_scanned=1, matches=[]),
        ]
        html = render_html(date(2026, 7, 10), results)
        assert "1 matches across 2 themes" in html
