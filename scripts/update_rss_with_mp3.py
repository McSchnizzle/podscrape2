#!/usr/bin/env python3
"""Insert a podcast item into the RSS feeds for simulated TTS outputs."""

import argparse
import datetime as dt
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"

ET.register_namespace('itunes', ITUNES_NS)
ET.register_namespace('content', CONTENT_NS)


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


def build_item(args: argparse.Namespace, pubdate: dt.datetime) -> ET.Element:
    item = ET.Element('item')
    ET.SubElement(item, 'title').text = args.title
    ET.SubElement(item, 'description').text = args.description
    ET.SubElement(item, 'pubDate').text = format_rss_date(pubdate)

    guid = ET.SubElement(item, 'guid')
    guid.text = args.guid
    guid.set('isPermaLink', 'false')

    enclosure = ET.SubElement(item, 'enclosure')
    enclosure.set('url', args.audio_url)
    enclosure.set('length', str(args.file_size))
    enclosure.set('type', 'audio/mpeg')

    ET.SubElement(item, f'{{{ITUNES_NS}}}title').text = args.title
    ET.SubElement(item, f'{{{ITUNES_NS}}}description').text = args.description
    ET.SubElement(item, f'{{{ITUNES_NS}}}duration').text = format_duration(args.duration_seconds)
    ET.SubElement(item, f'{{{ITUNES_NS}}}episodeType').text = args.episode_type

    if args.season is not None:
        ET.SubElement(item, f'{{{ITUNES_NS}}}season').text = str(args.season)
    if args.episode_number is not None:
        ET.SubElement(item, f'{{{ITUNES_NS}}}episode').text = str(args.episode_number)

    return item


def _indent(elem: ET.Element, level: int = 0, indent: str = "  ") -> None:
    """Recursively indent an ElementTree for pretty printing."""
    i = "\n" + indent * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + indent
        for child in elem:
            _indent(child, level + 1, indent)
        if not child.tail or not child.tail.strip():
            child.tail = i
    else:
        if not elem.text or not elem.text.strip():
            elem.text = ''
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = "\n" + indent * (level - 1)
    elif not elem.tail:
        elem.tail = "\n"


def insert_item(rss_path: Path, item: ET.Element, pubdate: dt.datetime) -> None:
    tree = ET.parse(rss_path)
    root = tree.getroot()
    channel = root.find('channel')
    if channel is None:
        raise RuntimeError(f'No <channel> element found in {rss_path}')

    # Update lastBuildDate
    last_build = channel.find('lastBuildDate')
    if last_build is None:
        last_build = ET.SubElement(channel, 'lastBuildDate')
    last_build.text = format_rss_date(pubdate)

    # Insert item before existing items (most recent first)
    children = list(channel)
    insert_index = None
    for idx, child in enumerate(children):
        if child.tag == 'item':
            insert_index = idx
            break
    if insert_index is None:
        channel.append(item)
    else:
        channel.insert(insert_index, item)

    _indent(root)
    rss_path.write_bytes(ET.tostring(root, encoding='utf-8', xml_declaration=True))


def main() -> None:
    args = parse_args()
    pubdate = dt.datetime.fromisoformat(args.pubdate.replace('Z', '+00:00'))
    item = build_item(args, pubdate)

    for path_str in args.output:
        path = Path(path_str)
        if not path.exists():
            raise FileNotFoundError(f'RSS file not found: {path}')
        insert_item(path, item, pubdate)


if __name__ == '__main__':
    main()
