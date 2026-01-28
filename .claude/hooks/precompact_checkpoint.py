#!/usr/bin/env python3
"""
PreCompact Hook: Saves conversation state before context compaction.

Extracts structured state from the conversation transcript and saves it
to PERSISTENT_STATE.yaml for restoration after compaction.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Try to import yaml, fall back to basic file ops if not available
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def get_project_dir():
    """Get the project directory from environment or current working directory."""
    return os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())


def get_checkpoint_dir():
    """Get the checkpoint directory path."""
    project_dir = get_project_dir()
    return Path(project_dir) / '.agents' / 'outputs' / 'claude_checkpoints'


def get_state_file():
    """Get the persistent state file path."""
    return get_checkpoint_dir() / 'PERSISTENT_STATE.yaml'


def extract_issue_numbers(text):
    """Extract issue/PR numbers from text."""
    patterns = [
        r'#(\d+)',
        r'[Ii]ssue\s*#?(\d+)',
        r'[Pp][Rr]\s*#?(\d+)',
        r'[Tt]icket\s*#?(\d+)',
    ]
    issues = set()
    for pattern in patterns:
        matches = re.findall(pattern, text)
        issues.update(matches)
    return sorted(list(issues))


def extract_phase(text):
    """Extract current work phase from text."""
    # Common phase patterns
    phase_patterns = [
        r'\b(MAP[-_]?PLAN|MAPPING|PLANNING)\b',
        r'\b(PATCH|PATCHING|IMPLEMENT|IMPLEMENTING)\b',
        r'\b(PROVE|PROVING|TEST|TESTING|VERIFY|VERIFYING)\b',
        r'\b(REVIEW|REVIEWING)\b',
        r'\b(DEPLOY|DEPLOYING)\b',
        r'\b(DEBUG|DEBUGGING)\b',
        r'\b(REFACTOR|REFACTORING)\b',
    ]

    # Search from end of text (most recent phase)
    text_lower = text.upper()
    for pattern in phase_patterns:
        matches = list(re.finditer(pattern, text_lower))
        if matches:
            return matches[-1].group(1).upper()
    return None


def extract_files_modified(text):
    """Extract file paths that were likely modified."""
    # Match common file patterns
    file_patterns = [
        r'(?:edited?|modified?|created?|updated?|changed?)\s+[`"\']?([a-zA-Z0-9_\-./]+\.[a-zA-Z0-9]+)[`"\']?',
        r'[`"\']([a-zA-Z0-9_\-./]+\.(?:py|js|ts|tsx|jsx|rs|go|java|rb|cpp|c|h|md|yaml|yml|json|toml))[`"\']',
    ]

    files = set()
    for pattern in file_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        files.update(matches)

    # Filter out obvious non-files
    filtered = []
    for f in files:
        if not any(x in f.lower() for x in ['http', 'www', 'example', 'test.test']):
            filtered.append(f)

    return sorted(filtered)[:20]  # Limit to 20 files


def extract_pending_tasks(text):
    """Extract TODO items and pending tasks."""
    patterns = [
        r'TODO[:\s]+(.+?)(?:\n|$)',
        r'FIXME[:\s]+(.+?)(?:\n|$)',
        r'(?:need to|should|must|will)\s+(.+?)(?:\.|$)',
        r'next[:\s]+(.+?)(?:\n|$)',
    ]

    tasks = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        tasks.extend(matches)

    # Clean and dedupe
    cleaned = []
    seen = set()
    for task in tasks:
        task = task.strip()[:100]  # Limit length
        if task and task.lower() not in seen:
            seen.add(task.lower())
            cleaned.append(task)

    return cleaned[:10]  # Limit to 10 tasks


def extract_key_decisions(text):
    """Extract key decisions made during the conversation."""
    patterns = [
        r'(?:decided|chosen?|going with|using|selected)\s+(.+?)(?:\.|$)',
        r'(?:will use|we\'ll use|I\'ll use)\s+(.+?)(?:\.|$)',
    ]

    decisions = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        decisions.extend(matches)

    # Clean and dedupe
    cleaned = []
    seen = set()
    for decision in decisions:
        decision = decision.strip()[:100]
        if decision and decision.lower() not in seen and len(decision) > 10:
            seen.add(decision.lower())
            cleaned.append(decision)

    return cleaned[:5]  # Limit to 5 decisions


def extract_current_branch(text):
    """Extract current git branch if mentioned."""
    patterns = [
        r'(?:branch|on)\s+[`"\']?([a-zA-Z0-9_\-/]+)[`"\']?',
        r'git checkout\s+[`"\']?([a-zA-Z0-9_\-/]+)[`"\']?',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Return the most recent branch mention
            return matches[-1]
    return None


def extract_learned_patterns(text):
    """Extract patterns learned during the conversation - errors, solutions, gotchas."""
    patterns_found = {
        'errors': [],
        'solutions': [],
        'gotchas': [],
        'useful_commands': []
    }

    # Error patterns - things that failed
    error_patterns = [
        r'(?:error|failed|failure|exception|bug|issue)[:\s]+(.+?)(?:\n|$)',
        r'(?:doesn\'t work|didn\'t work|not working|broken)[:\s]*(.+?)(?:\.|$)',
        r'(?:problem|trouble)[:\s]+(.+?)(?:\n|$)',
    ]
    for pattern in error_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            clean = match.strip()[:150]
            if clean and len(clean) > 15:
                patterns_found['errors'].append(clean)

    # Solution patterns - things that fixed issues
    solution_patterns = [
        r'(?:fixed by|solved by|solution was|the fix was|worked after)[:\s]+(.+?)(?:\.|$)',
        r'(?:had to|needed to)\s+(.+?)(?:to fix|to solve|to resolve)',
        r'(?:this worked|that worked)[:\s]*(.+?)(?:\.|$)',
    ]
    for pattern in solution_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            clean = match.strip()[:150]
            if clean and len(clean) > 10:
                patterns_found['solutions'].append(clean)

    # Gotcha patterns - unexpected behaviors or important notes
    gotcha_patterns = [
        r'(?:gotcha|watch out|be careful|note that|important)[:\s]+(.+?)(?:\.|$)',
        r'(?:turns out|actually|surprisingly)[,\s]+(.+?)(?:\.|$)',
        r'(?:don\'t forget|remember to|make sure to)[:\s]+(.+?)(?:\.|$)',
    ]
    for pattern in gotcha_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            clean = match.strip()[:150]
            if clean and len(clean) > 10:
                patterns_found['gotchas'].append(clean)

    # Useful commands that were run successfully
    command_patterns = [
        r'`([a-zA-Z0-9_\-./\s]{5,80})`\s*(?:worked|succeeded|fixed)',
        r'(?:run|running|ran)\s+`([^`]{5,80})`',
    ]
    for pattern in command_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            clean = match.strip()
            if clean and not any(x in clean.lower() for x in ['http', 'example']):
                patterns_found['useful_commands'].append(clean)

    # Dedupe each category
    for key in patterns_found:
        seen = set()
        deduped = []
        for item in patterns_found[key]:
            if item.lower() not in seen:
                seen.add(item.lower())
                deduped.append(item)
        patterns_found[key] = deduped[:5]  # Limit to 5 per category

    return patterns_found


def get_patterns_file():
    """Get the critical patterns file path."""
    project_dir = get_project_dir()
    return Path(project_dir) / '.claude' / 'memory' / 'patterns-critical.md'


def update_patterns_file(learned_patterns):
    """Append newly learned patterns to patterns-critical.md without duplicating."""
    patterns_file = get_patterns_file()

    if not patterns_file.exists():
        return

    # Read existing content
    try:
        with open(patterns_file, 'r') as f:
            existing_content = f.read()
    except Exception:
        return

    # Check if we have anything new to add
    has_new_content = any(learned_patterns.get(k) for k in learned_patterns)
    if not has_new_content:
        return

    # Build new section
    new_lines = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Only add sections that have content and aren't already in the file
    if learned_patterns.get('errors'):
        for error in learned_patterns['errors']:
            if error.lower()[:50] not in existing_content.lower():
                if not new_lines:
                    new_lines.append(f"\n\n### Learned Patterns ({timestamp})\n")
                new_lines.append(f"- **Error encountered**: {error}")

    if learned_patterns.get('solutions'):
        for solution in learned_patterns['solutions']:
            if solution.lower()[:50] not in existing_content.lower():
                if not new_lines:
                    new_lines.append(f"\n\n### Learned Patterns ({timestamp})\n")
                new_lines.append(f"- **Solution**: {solution}")

    if learned_patterns.get('gotchas'):
        for gotcha in learned_patterns['gotchas']:
            if gotcha.lower()[:50] not in existing_content.lower():
                if not new_lines:
                    new_lines.append(f"\n\n### Learned Patterns ({timestamp})\n")
                new_lines.append(f"- **Gotcha**: {gotcha}")

    if learned_patterns.get('useful_commands'):
        for cmd in learned_patterns['useful_commands']:
            if cmd.lower() not in existing_content.lower():
                if not new_lines:
                    new_lines.append(f"\n\n### Learned Patterns ({timestamp})\n")
                new_lines.append(f"- **Useful command**: `{cmd}`")

    # Append to file if we have new content
    if new_lines:
        try:
            with open(patterns_file, 'a') as f:
                f.write('\n'.join(new_lines) + '\n')
        except Exception as e:
            print(f"Warning: Could not update patterns file: {e}", file=sys.stderr)


def load_transcript(transcript_path):
    """Load and parse transcript from file."""
    try:
        with open(transcript_path, 'r') as f:
            content = f.read()

        # Try to parse as JSON lines
        lines = content.strip().split('\n')
        messages = []
        for line in lines:
            try:
                msg = json.loads(line)
                messages.append(msg)
            except json.JSONDecodeError:
                continue

        # Extract text content from messages
        text_parts = []
        for msg in messages[-300:]:  # Last 300 messages
            if isinstance(msg, dict):
                if 'content' in msg:
                    content = msg['content']
                    if isinstance(content, str):
                        text_parts.append(content)
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and 'text' in item:
                                text_parts.append(item['text'])
                            elif isinstance(item, str):
                                text_parts.append(item)

        return '\n'.join(text_parts)
    except Exception as e:
        print(f"Warning: Could not load transcript: {e}", file=sys.stderr)
        return ""


def save_state(state):
    """Save state to YAML file."""
    state_file = get_state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)

    if HAS_YAML:
        with open(state_file, 'w') as f:
            yaml.dump(state, f, default_flow_style=False, sort_keys=False)
    else:
        # Fallback: write simple YAML manually
        with open(state_file, 'w') as f:
            f.write("# Auto-generated state file\n")
            f.write(f"# Updated: {state.get('last_updated', 'unknown')}\n\n")
            write_yaml_simple(f, state)


def write_yaml_simple(f, data, indent=0):
    """Write simple YAML without the yaml library."""
    prefix = "  " * indent
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)) and value:
                f.write(f"{prefix}{key}:\n")
                write_yaml_simple(f, value, indent + 1)
            elif isinstance(value, list):
                f.write(f"{prefix}{key}: []\n")
            elif value is None:
                f.write(f"{prefix}{key}: null\n")
            else:
                f.write(f"{prefix}{key}: {value}\n")
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                f.write(f"{prefix}-\n")
                write_yaml_simple(f, item, indent + 1)
            else:
                f.write(f"{prefix}- {item}\n")


def save_transcript_backup(transcript_path):
    """Save a backup of the raw transcript."""
    if not transcript_path or not os.path.exists(transcript_path):
        return None

    checkpoint_dir = get_checkpoint_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = checkpoint_dir / f"{timestamp}.transcript.jsonl"

    try:
        with open(transcript_path, 'r') as src:
            with open(backup_path, 'w') as dst:
                dst.write(src.read())
        return backup_path
    except Exception as e:
        print(f"Warning: Could not backup transcript: {e}", file=sys.stderr)
        return None


def save_markdown_summary(state):
    """Save a human-readable markdown checkpoint."""
    checkpoint_dir = get_checkpoint_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    summary_path = checkpoint_dir / f"{timestamp}.checkpoint.md"

    try:
        with open(summary_path, 'w') as f:
            f.write(f"# Checkpoint: {state.get('last_updated', 'unknown')}\n\n")

            active = state.get('active_work', {})
            f.write("## Active Work\n")
            f.write(f"- **Issue**: {active.get('issue', 'None')}\n")
            f.write(f"- **Branch**: {active.get('branch', 'unknown')}\n")
            f.write(f"- **Phase**: {active.get('phase', 'None')}\n")
            f.write(f"- **Last Action**: {active.get('last_action', 'None')}\n\n")

            files = state.get('files_modified', [])
            if files:
                f.write("## Files Modified\n")
                for file in files:
                    f.write(f"- `{file}`\n")
                f.write("\n")

            tasks = state.get('pending_tasks', [])
            if tasks:
                f.write("## Pending Tasks\n")
                for task in tasks:
                    f.write(f"- {task}\n")
                f.write("\n")

            decisions = state.get('key_decisions', [])
            if decisions:
                f.write("## Key Decisions\n")
                for decision in decisions:
                    f.write(f"- {decision}\n")
                f.write("\n")

        return summary_path
    except Exception as e:
        print(f"Warning: Could not save summary: {e}", file=sys.stderr)
        return None


def main():
    """Main entry point for the PreCompact hook."""
    # Read hook input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        input_data = {}

    transcript_path = input_data.get('transcript_path')

    # Load and parse transcript
    transcript_text = ""
    if transcript_path:
        transcript_text = load_transcript(transcript_path)

    # Extract state from transcript
    issues = extract_issue_numbers(transcript_text)
    phase = extract_phase(transcript_text)
    files = extract_files_modified(transcript_text)
    tasks = extract_pending_tasks(transcript_text)
    decisions = extract_key_decisions(transcript_text)
    branch = extract_current_branch(transcript_text)

    # Build state object
    state = {
        'last_updated': datetime.now().isoformat(),
        'active_work': {
            'issue': issues[0] if issues else None,
            'all_issues': issues if len(issues) > 1 else None,
            'branch': branch or 'unknown',
            'phase': phase,
            'last_action': tasks[0] if tasks else None,
        },
        'files_modified': files,
        'pending_tasks': tasks,
        'key_decisions': decisions,
    }

    # Clean up None values in active_work
    state['active_work'] = {k: v for k, v in state['active_work'].items() if v is not None}

    # Save state
    save_state(state)

    # Save transcript backup
    if transcript_path:
        save_transcript_backup(transcript_path)

    # Save markdown summary
    save_markdown_summary(state)

    # Extract and save learned patterns
    learned_patterns = extract_learned_patterns(transcript_text)
    update_patterns_file(learned_patterns)

    print(f"Checkpoint saved at {datetime.now().isoformat()}", file=sys.stderr)


if __name__ == '__main__':
    main()
