"""
Subtitle Parser Utility

Parses VTT/SRT subtitle files to plain text.
Used by yt-dlp transcript fetcher to convert downloaded subtitles.
"""

import re
from dataclasses import dataclass


@dataclass
class ParsedSubtitle:
    """Result of parsing a subtitle file."""
    text: str
    word_count: int
    line_count: int


def parse_vtt(content: str) -> ParsedSubtitle:
    """Parse WebVTT subtitle content to plain text."""
    lines = content.split('\n')
    text_lines = []
    in_cue = False

    for line in lines:
        line = line.strip()

        if not line:
            in_cue = False
            continue
        if line.startswith('WEBVTT'):
            continue
        if line.startswith('NOTE'):
            continue
        if '-->' in line:
            in_cue = True
            continue
        if re.match(r'^[\d\w-]+$', line) and not in_cue:
            continue
        if line.startswith('Kind:') or line.startswith('Language:'):
            continue

        if in_cue:
            clean_line = re.sub(r'<[^>]+>', '', line)
            clean_line = re.sub(r'\{[^}]+\}', '', clean_line)
            if clean_line.strip():
                text_lines.append(clean_line.strip())

    # Deduplicate consecutive identical lines (VTT often has overlapping cues)
    deduped_lines = []
    prev_line = None
    for line in text_lines:
        if line != prev_line:
            deduped_lines.append(line)
            prev_line = line

    text = ' '.join(deduped_lines)
    text = re.sub(r'\s+', ' ', text).strip()
    word_count = len(text.split()) if text else 0

    return ParsedSubtitle(text=text, word_count=word_count, line_count=len(deduped_lines))


def parse_srt(content: str) -> ParsedSubtitle:
    """Parse SRT subtitle content to plain text."""
    lines = content.split('\n')
    text_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(r'^\d+$', line):
            continue
        if '-->' in line:
            continue

        clean_line = re.sub(r'<[^>]+>', '', line)
        clean_line = re.sub(r'\{[^}]+\}', '', clean_line)
        if clean_line.strip():
            text_lines.append(clean_line.strip())

    deduped_lines = []
    prev_line = None
    for line in text_lines:
        if line != prev_line:
            deduped_lines.append(line)
            prev_line = line

    text = ' '.join(deduped_lines)
    text = re.sub(r'\s+', ' ', text).strip()
    word_count = len(text.split()) if text else 0

    return ParsedSubtitle(text=text, word_count=word_count, line_count=len(deduped_lines))


def parse_subtitle_file(filepath: str) -> ParsedSubtitle:
    """Parse a subtitle file to plain text, auto-detecting format."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    if filepath.endswith('.vtt') or content.strip().startswith('WEBVTT'):
        return parse_vtt(content)
    elif filepath.endswith('.srt'):
        return parse_srt(content)
    else:
        # Default to VTT
        return parse_vtt(content)
