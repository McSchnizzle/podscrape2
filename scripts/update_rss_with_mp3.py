#!/usr/bin/env python3
"""Insert a podcast item into the RSS feeds for simulated TTS outputs.

Designed to make minimal edits so git diffs only include the newly added
`<item>` block and updated `<lastBuildDate>` values. Avoids reformatting
the rest of the XML by working with string splicing instead of rebuilding
the entire tree.
"""

import argparse
import datetime as dt
import re
from pathlib import Path
from xml.sax.saxutils import escape


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add an episode item to RSS feeds")
    parser.add_argument('--title', required=True, help='Episode title')
    parser.add_argument('--description', required=True, help='Episode description')
    parser.add_argument('--audio-url', required=True, help='Public URL for the MP3 asset')
    parser.add_argument('--file-size', type=int, required=True, help='MP3 file size in bytes')
    parser.add_argument('--duration-seconds', type=int, default=60, help='Episode duration in seconds')
    parser.add_argument('--guid', required=True, help='Unique identifier for the episode')
    parser.add_argument('--pubdate', required=True,
                        help='Publication datetime in ISO8601 (e.g. 2025-09-19T13:40:25Z)')
    parser.add_argument('--season', type=int, default=None)
    parser.add_argument('--episode-number', type=int, default=None)
    parser.add_argument('--episode-type', default='full')
    parser.add_argument('--output', nargs='+', default=[
        'data/rss/daily-digest.xml',
        'public/daily-digest.xml'
    ], help='RSS files to update')
    return parser.parse_args()


def format_rss_date(pubdate: dt.datetime) -> str:
    if pubdate.tzinfo is None:
        pubdate = pubdate.replace(tzinfo=dt.timezone.utc)
    else:
        pubdate = pubdate.astimezone(dt.timezone.utc)
    return pubdate.strftime('%a, %d %b %Y %H:%M:%S %z')


def format_duration(seconds: int) -> str:
    seconds = max(0, seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def build_item_xml(args: argparse.Namespace, pubdate: dt.datetime) -> str:
    """Return a pre-indented XML fragment representing the new item."""

    def esc(value: str) -> str:
        return escape(value, {'"': '&quot;'})

    lines = [
        "    <item>",
        f"      <title>{esc(args.title)}</title>",
        f"      <description>{esc(args.description)}</description>",
        f"      <pubDate>{format_rss_date(pubdate)}</pubDate>",
        f"      <guid isPermaLink=\"false\">{esc(args.guid)}</guid>",
        f"      <enclosure url=\"{esc(args.audio_url)}\" length=\"{args.file_size}\" type=\"audio/mpeg\"/>",
        f"      <itunes:title>{esc(args.title)}</itunes:title>",
        f"      <itunes:description>{esc(args.description)}</itunes:description>",
        f"      <itunes:duration>{format_duration(args.duration_seconds)}</itunes:duration>",
        f"      <itunes:episodeType>{esc(args.episode_type)}</itunes:episodeType>",
    ]

    if args.season is not None:
        lines.append(f"      <itunes:season>{args.season}</itunes:season>")
    if args.episode_number is not None:
        lines.append(f"      <itunes:episode>{args.episode_number}</itunes:episode>")

    lines.append("    </item>")
    return "\n".join(lines) + "\n"


LAST_BUILD_RE = re.compile(r"(<lastBuildDate>)(.*?)(</lastBuildDate>)", re.DOTALL)


def insert_item(rss_path: Path, item_xml: str, pubdate: dt.datetime, guid: str) -> None:
    text = rss_path.read_text()

    if guid in text:
        print(f"GUID {guid} already present in {rss_path}, skipping")
        return

    last_build = format_rss_date(pubdate)
    if LAST_BUILD_RE.search(text):
        text = LAST_BUILD_RE.sub(rf"\1{last_build}\3", text, count=1)
    else:
        raise RuntimeError(f"No <lastBuildDate> element found in {rss_path}")

    item_marker = "  <item>"
    insert_at = text.find(item_marker)
    if insert_at == -1:
        insert_at = text.find("</channel>")
        if insert_at == -1:
            raise RuntimeError(f"No insertion point found in {rss_path}")
        prefix = "" if text[:insert_at].endswith("\n") else "\n"
        new_text = text[:insert_at] + prefix + item_xml + text[insert_at:]
    else:
        prefix = "" if text[:insert_at].endswith("\n") else "\n"
        new_text = text[:insert_at] + prefix + item_xml + text[insert_at:]

    rss_path.write_text(new_text)


def main() -> None:
    args = parse_args()
    pubdate = dt.datetime.fromisoformat(args.pubdate.replace('Z', '+00:00'))
    for path_str in args.output:
        path = Path(path_str)
        if not path.exists():
            raise FileNotFoundError(f'RSS file not found: {path}')
        insert_item(path, build_item_xml(args, pubdate), pubdate, args.guid)


if __name__ == '__main__':
    main()
