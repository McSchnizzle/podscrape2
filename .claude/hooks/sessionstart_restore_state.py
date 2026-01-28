#!/usr/bin/env python3
"""
SessionStart Hook: Restores conversation state after compaction or session start.

Loads saved state from PERSISTENT_STATE.yaml and critical patterns,
then outputs them for Claude to incorporate into the new context.
"""

import json
import os
import sys
from pathlib import Path

# Try to import yaml, fall back to basic parsing if not available
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def get_project_dir():
    """Get the project directory from environment or current working directory."""
    return os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())


def get_state_file():
    """Get the persistent state file path."""
    project_dir = get_project_dir()
    return Path(project_dir) / '.agents' / 'outputs' / 'claude_checkpoints' / 'PERSISTENT_STATE.yaml'


def get_patterns_file():
    """Get the critical patterns file path."""
    project_dir = get_project_dir()
    return Path(project_dir) / '.claude' / 'memory' / 'patterns-critical.md'


def load_yaml_file(filepath):
    """Load a YAML file, with fallback for missing yaml library."""
    if not filepath.exists():
        return None

    try:
        with open(filepath, 'r') as f:
            content = f.read()

        if HAS_YAML:
            return yaml.safe_load(content)
        else:
            # Very basic YAML parsing fallback
            return parse_simple_yaml(content)
    except Exception as e:
        print(f"Warning: Could not load {filepath}: {e}", file=sys.stderr)
        return None


def parse_simple_yaml(content):
    """Parse simple YAML without the yaml library."""
    result = {}
    current_key = None
    current_list = None

    for line in content.split('\n'):
        line = line.rstrip()
        if not line or line.startswith('#'):
            continue

        # Count indentation
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if stripped.startswith('- '):
            # List item
            if current_list is not None:
                current_list.append(stripped[2:])
        elif ':' in stripped:
            parts = stripped.split(':', 1)
            key = parts[0].strip()
            value = parts[1].strip() if len(parts) > 1 else ''

            if value == '' or value == '[]':
                # Start of nested structure or empty list
                if indent == 0:
                    result[key] = {}
                    current_key = key
                    current_list = None
                elif current_key:
                    if value == '[]':
                        result[current_key][key] = []
                    else:
                        result[current_key][key] = {}
                        current_list = []
                        result[current_key][key] = current_list
            elif value == 'null' or value == 'None':
                if indent == 0:
                    result[key] = None
                elif current_key:
                    result[current_key][key] = None
            else:
                if indent == 0:
                    result[key] = value
                    current_key = None
                    current_list = None
                elif current_key:
                    result[current_key][key] = value

    return result


def load_patterns():
    """Load critical patterns file."""
    patterns_file = get_patterns_file()
    if not patterns_file.exists():
        return None

    try:
        with open(patterns_file, 'r') as f:
            return f.read()
    except Exception as e:
        print(f"Warning: Could not load patterns: {e}", file=sys.stderr)
        return None


def format_state_output(state):
    """Format the state for output to Claude."""
    if not state:
        return None

    lines = []
    lines.append("## Restored Work State")
    lines.append("")

    active = state.get('active_work', {})
    if active:
        if active.get('issue'):
            lines.append(f"**Active Issue**: #{active['issue']}")
        if active.get('all_issues'):
            lines.append(f"**Related Issues**: {', '.join(['#' + i for i in active['all_issues']])}")
        if active.get('branch') and active['branch'] != 'unknown':
            lines.append(f"**Branch**: `{active['branch']}`")
        if active.get('phase'):
            lines.append(f"**Phase**: {active['phase']}")
        if active.get('last_action'):
            lines.append(f"**Last Action**: {active['last_action']}")
        lines.append("")

    files = state.get('files_modified', [])
    if files:
        lines.append("**Files Modified**:")
        for f in files[:10]:  # Limit output
            lines.append(f"- `{f}`")
        lines.append("")

    tasks = state.get('pending_tasks', [])
    if tasks:
        lines.append("**Pending Tasks**:")
        for task in tasks[:5]:  # Limit output
            lines.append(f"- {task}")
        lines.append("")

    decisions = state.get('key_decisions', [])
    if decisions:
        lines.append("**Key Decisions**:")
        for decision in decisions[:3]:  # Limit output
            lines.append(f"- {decision}")
        lines.append("")

    if state.get('last_updated'):
        lines.append(f"*State saved: {state['last_updated']}*")

    return '\n'.join(lines)


def format_continue_instructions(state):
    """Generate continue instructions if active workflow detected."""
    if not state:
        return None

    active = state.get('active_work', {})
    issue = active.get('issue')
    phase = active.get('phase')

    if not issue and not phase:
        return None

    lines = []
    lines.append("---")
    lines.append("## Continue Instructions")
    lines.append("")

    if issue and phase:
        lines.append(f"You were working on **Issue #{issue}** in the **{phase}** phase.")
    elif issue:
        lines.append(f"You were working on **Issue #{issue}**.")
    elif phase:
        lines.append(f"You were in the **{phase}** phase.")

    tasks = state.get('pending_tasks', [])
    if tasks:
        lines.append(f"Next task: {tasks[0]}")

    lines.append("")
    lines.append("Please continue from where you left off.")

    return '\n'.join(lines)


def main():
    """Main entry point for the SessionStart hook."""
    # Read hook input from stdin (contains source info)
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        input_data = {}

    source = input_data.get('source', 'unknown')

    output_parts = []

    # Load and format state
    state_file = get_state_file()
    state = load_yaml_file(state_file)

    if state:
        state_output = format_state_output(state)
        if state_output:
            output_parts.append("```")
            output_parts.append(state_output)
            output_parts.append("```")

    # Load critical patterns
    patterns = load_patterns()
    if patterns:
        output_parts.append("")
        output_parts.append("## Critical Patterns")
        output_parts.append("")
        output_parts.append(patterns.strip())

    # Add continue instructions if active workflow
    if state:
        continue_inst = format_continue_instructions(state)
        if continue_inst:
            output_parts.append("")
            output_parts.append(continue_inst)

    # Output everything
    if output_parts:
        print('\n'.join(output_parts))
    else:
        # No state to restore - just a brief message
        if source == 'compact':
            print("*Session restored after context compaction. No previous state found.*")


if __name__ == '__main__':
    main()
