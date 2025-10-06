"""
Migration script to parse master-tasklist.md and COMPLETED_TASKS_SUMMARY.md
and populate the tasks table in the database.

Usage:
    python3 scripts/migrate_tasks_to_database.py [--dry-run]
"""

import os
import re
import sys
from datetime import datetime
from typing import List, Dict, Optional
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')


class Task:
    """Represents a task to be inserted into the database."""

    def __init__(
        self,
        title: str,
        description: str = "",
        status: str = "open",
        priority: str = "P3",
        category: str = None,
        version_introduced: str = None,
        version_completed: str = None,
        files_affected: List[str] = None,
        completion_notes: str = None,
        session_number: int = None,
        tags: List[str] = None
    ):
        self.title = title
        self.description = description
        self.status = status
        self.priority = priority
        self.category = category
        self.version_introduced = version_introduced
        self.version_completed = version_completed
        self.files_affected = files_affected or []
        self.completion_notes = completion_notes
        self.session_number = session_number
        self.tags = tags or []


def parse_master_tasklist(file_path: str) -> List[Task]:
    """Parse master-tasklist.md and extract open tasks."""

    tasks = []

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract version from header
    version_match = re.search(r'\*\*Last Updated\*\*: .+ \((v[\d.]+)\)', content)
    current_version = version_match.group(1) if version_match else None

    # Split content into priority sections by looking for "## MEDIUM (P2)" style headers
    sections = re.split(r'(?=## (?:CRITICAL|HIGH|MEDIUM|LOW) \(P\d\))', content)

    for section in sections:
        if not section.strip():
            continue

        # Identify priority and category from section header
        header_match = re.search(r'## (CRITICAL|HIGH|MEDIUM|LOW) \((P\d)\) - (.+?):', section)
        if not header_match:
            continue

        priority_name = header_match.group(1)
        priority = header_match.group(2)
        category = header_match.group(3).strip()

        # Skip sections marked as all completed
        if '0 REMAINING' in section or '**All P' in section and 'completed' in section.lower():
            continue

        # Extract individual tasks using ### numbering
        task_pattern = r'### (\d+)\.\s+(.+?)\n(.*?)(?=\n### \d+\.|\n## |$)'
        task_matches = re.finditer(task_pattern, section, re.DOTALL)

        for match in task_matches:
            task_num = match.group(1)
            title = match.group(2).strip()
            body = match.group(3).strip()

            # Skip if explicitly marked as completed
            if '✅' in body:
                continue

            # Build description from bullet points
            description_lines = []
            files = []
            tags = []

            for line in body.split('\n'):
                line = line.strip()
                if not line or line.startswith('**Latest Completion'):
                    continue

                # Extract file references
                if '**File' in line or '**Files' in line:
                    file_matches = re.findall(r'`([^`]+\.py[^`]*)`', line)
                    files.extend(file_matches)

                # Build description from bullet points
                if line.startswith('- **'):
                    description_lines.append(line)

            description = '\n'.join(description_lines) if description_lines else body[:500]

            # Determine status
            status = 'open'
            if '❌ Not implemented' in body:
                status = 'open'
            elif '🔄 Partially implemented' in body or 'needs completion' in body.lower():
                status = 'in_progress'

            # Extract tags
            body_lower = body.lower()
            if 'database' in body_lower or 'database-first' in body_lower:
                tags.append('database')
            if 'performance' in body_lower or 'optimization' in body_lower:
                tags.append('performance')
            if 'architecture' in body_lower:
                tags.append('architecture')

            task = Task(
                title=title,
                description=description,
                status=status,
                priority=priority,
                category=category,
                version_introduced=current_version,
                files_affected=files,
                tags=list(set(tags))  # Remove duplicates
            )
            tasks.append(task)

    return tasks


def parse_completed_tasks_summary(file_path: str) -> List[Task]:
    """Parse COMPLETED_TASKS_SUMMARY.md and extract completed tasks."""

    tasks = []

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract version from header
    version_match = re.search(r'\*\*Version\*\*: (v[\d.]+)', content)
    current_version = version_match.group(1) if version_match else None

    # Split into priority sections
    sections = re.split(r'(?=## .+ \(P\d\))', content)

    for section in sections:
        if not section.strip() or '### ✅ COMPLETED:' not in section:
            continue

        # Extract priority from section header
        priority_match = re.search(r'## .+ \((P\d)\) - (.+?):', section)
        if not priority_match:
            continue

        priority = priority_match.group(1)
        category = priority_match.group(2).strip()

        # Extract session number if present
        session_match = re.search(r'SESSION (\d+)', section.upper())
        session_num = int(session_match.group(1)) if session_match else None

        # Find all numbered tasks (1. **Title**)
        task_pattern = r'^\d+\.\s+\*\*(.+?)\*\*'
        lines = section.split('\n')

        current_task = None
        current_body = []

        for line in lines:
            task_match = re.match(task_pattern, line.strip())
            if task_match:
                # Save previous task if exists
                if current_task:
                    tasks.append(create_completed_task(
                        current_task, '\n'.join(current_body), priority,
                        category, current_version, session_num
                    ))

                # Start new task
                current_task = task_match.group(1).strip()
                current_body = []
            elif current_task and line.strip():
                current_body.append(line.strip())

        # Don't forget the last task
        if current_task:
            tasks.append(create_completed_task(
                current_task, '\n'.join(current_body), priority,
                category, current_version, session_num
            ))

    return tasks


def create_completed_task(title: str, body: str, priority: str, category: str,
                         version: str, session_num: Optional[int]) -> Task:
    """Helper function to create a completed Task object."""

    # Extract version from title if present (e.g., "(v1.33)")
    version_completed = version
    version_match = re.search(r'\(v([\d.]+)\)', title)
    if version_match:
        version_completed = f'v{version_match.group(1)}'
        title = re.sub(r'\s*\(v[\d.]+\)', '', title)

    # Extract file references
    files = re.findall(r'(?:File|Files):\s*`?([^`\n]+\.(?:py|ts|tsx|yml|yaml|md|json)[^`\n,]*)', body)

    # Build description and completion notes
    description_lines = []
    for line in body.split('\n'):
        if line.startswith('-'):
            description_lines.append(line)

    description = '\n'.join(description_lines[:5])  # First 5 bullet points
    completion_notes = '\n'.join(description_lines[:15])  # More detail for notes

    # Extract tags
    tags = []
    body_lower = body.lower()
    if 'database' in body_lower or 'database-first' in body_lower:
        tags.append('database')
    if 'security' in body_lower or 'rls' in body_lower:
        tags.append('security')
    if 'performance' in body_lower or 'optimization' in body_lower:
        tags.append('performance')
    if 'workflow' in body_lower or 'github' in body_lower:
        tags.append('ci-cd')

    return Task(
        title=title,
        description=description,
        status='completed',
        priority=priority,
        category=category,
        version_completed=version_completed,
        files_affected=files[:15],
        completion_notes=completion_notes,
        session_number=session_num,
        tags=list(set(tags))
    )


def insert_tasks_to_database(tasks: List[Task], dry_run: bool = False):
    """Insert tasks into the database."""

    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment")
        sys.exit(1)

    engine = create_engine(db_url)

    print(f"\n{'=' * 60}")
    print(f"Found {len(tasks)} tasks to insert")
    print(f"{'=' * 60}\n")

    if dry_run:
        print("DRY RUN MODE - No changes will be made to the database\n")
        for i, task in enumerate(tasks, 1):
            print(f"{i}. [{task.priority}] {task.title}")
            print(f"   Status: {task.status}")
            print(f"   Category: {task.category}")
            if task.files_affected:
                print(f"   Files: {len(task.files_affected)} file(s)")
            print()
        return

    # Insert tasks
    inserted_count = 0
    with engine.connect() as conn:
        for task in tasks:
            try:
                result = conn.execute(text("""
                    INSERT INTO tasks (
                        title, description, status, priority, category,
                        version_introduced, version_completed, files_affected,
                        completion_notes, session_number, tags
                    ) VALUES (
                        :title, :description, :status, :priority, :category,
                        :version_introduced, :version_completed, :files_affected,
                        :completion_notes, :session_number, :tags
                    )
                """), {
                    'title': task.title,
                    'description': task.description,
                    'status': task.status,
                    'priority': task.priority,
                    'category': task.category,
                    'version_introduced': task.version_introduced,
                    'version_completed': task.version_completed,
                    'files_affected': task.files_affected if task.files_affected else None,
                    'completion_notes': task.completion_notes,
                    'session_number': task.session_number,
                    'tags': task.tags if task.tags else None
                })
                inserted_count += 1
                print(f"✓ Inserted: [{task.priority}] {task.title[:60]}...")

            except Exception as e:
                print(f"✗ Failed to insert '{task.title[:40]}...': {e}")

        conn.commit()

    print(f"\n{'=' * 60}")
    print(f"Successfully inserted {inserted_count}/{len(tasks)} tasks")
    print(f"{'=' * 60}\n")


def main():
    """Main execution function."""

    dry_run = '--dry-run' in sys.argv

    print("\n" + "=" * 60)
    print("Task Migration Script")
    print("=" * 60)

    # Parse markdown files
    print("\nParsing master-tasklist.md...")
    open_tasks = parse_master_tasklist('master-tasklist.md')
    print(f"  Found {len(open_tasks)} open tasks")

    print("\nParsing COMPLETED_TASKS_SUMMARY.md...")
    completed_tasks = parse_completed_tasks_summary('COMPLETED_TASKS_SUMMARY.md')
    print(f"  Found {len(completed_tasks)} completed tasks")

    # Combine all tasks
    all_tasks = open_tasks + completed_tasks

    # Insert into database
    insert_tasks_to_database(all_tasks, dry_run=dry_run)

    if not dry_run:
        print("Migration complete! ✓")
        print("\nYou can now view tasks in the web UI at: http://localhost:3000/maintenance")
    else:
        print("Run without --dry-run to insert tasks into the database")


if __name__ == '__main__':
    main()
