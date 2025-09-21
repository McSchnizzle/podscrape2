#!/usr/bin/env python3
"""Backfill topics and instructions from config/topics.json into Supabase."""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any
import re

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from src.config.config_manager import ConfigManager
from src.database.models import get_topic_repo, Topic


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower())
    return slug.strip('-') or "topic"


def load_topics_config(config_path: Path) -> Dict[str, Any]:
    with config_path.open('r', encoding='utf-8') as fh:
        return json.load(fh)


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate config topics to Supabase")
    parser.add_argument('--config', default=PROJECT_ROOT / 'config' / 'topics.json',
                        type=Path, help='Path to topics.json')
    parser.add_argument('--instructions-dir', default=PROJECT_ROOT / 'digest_instructions',
                        type=Path, help='Directory containing markdown instruction files')
    parser.add_argument('--change-note', default='Initial import from topics.json',
                        help='Change note to store with instruction versions')
    parser.add_argument('--created-by', default='migration-script',
                        help='Identifier stored as the creator of the instruction version')
    parser.add_argument('--dry-run', action='store_true', help='Preview actions without writing to the database')
    args = parser.parse_args()

    config_path: Path = args.config
    instructions_dir: Path = args.instructions_dir

    if not config_path.exists():
        raise SystemExit(f"Config file not found: {config_path}")
    if not instructions_dir.exists():
        raise SystemExit(f"Instructions directory not found: {instructions_dir}")

    config = ConfigManager(config_dir=config_path.parent)
    topics_data = load_topics_config(config_path)
    default_voice_settings = topics_data.get('settings', {}).get('default_voice_settings', {})

    topic_repo = get_topic_repo()

    migrated = []
    for index, topic_entry in enumerate(topics_data.get('topics', []), start=1):
        name = topic_entry.get('name')
        if not name:
            continue

        slug = topic_entry.get('slug') or slugify(name)
        instruction_file = topic_entry.get('instruction_file')
        instructions_md = None
        if instruction_file:
            instruction_path = instructions_dir / instruction_file
            if instruction_path.exists():
                instructions_md = instruction_path.read_text(encoding='utf-8')
            else:
                print(f"Warning: instruction file missing -> {instruction_path}")

        topic_obj = Topic(
            slug=slug,
            name=name,
            description=topic_entry.get('description'),
            voice_id=topic_entry.get('voice_id'),
            voice_settings=topic_entry.get('voice_settings') or default_voice_settings,
            instructions_md=instructions_md,
            is_active=topic_entry.get('active', True),
            sort_order=index * 10,
        )

        migrated.append({
            'slug': slug,
            'name': name,
            'instruction_file': instruction_file,
            'has_instructions': bool(instructions_md),
            'active': topic_obj.is_active,
        })

        if args.dry_run:
            continue

        saved_topic = topic_repo.upsert_topic(topic_obj)
        if instructions_md:
            topic_repo.update_instructions(
                topic_id=saved_topic.id,
                instructions_md=instructions_md,
                change_note=args.change_note,
                created_by=args.created_by,
            )

    print("Topics processed:")
    for row in migrated:
        print(f" - {row['name']} ({row['slug']}), instructions={'yes' if row['has_instructions'] else 'no'}")

    if args.dry_run:
        print("Dry run finished. No database changes were made.")
    else:
        print("Migration completed.")


if __name__ == '__main__':
    main()
