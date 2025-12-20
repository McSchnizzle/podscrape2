"""
Phase output contract utilities for deterministic JSON output.

Provides a clean separation between log output (stdout) and structured
results (file or stdout based on configuration).
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def write_phase_result(result: Dict[str, Any], output_path: Optional[str] = None) -> None:
    """
    Write phase result to the configured output channel.

    Args:
        result: Dictionary containing phase execution results
        output_path: Optional path to write JSON file. If None, writes to stdout.

    Raises:
        IOError: If file write fails when output_path is specified
    """
    json_str = json.dumps(result)

    if output_path:
        # Write to file (deterministic output channel)
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json_str, encoding='utf-8')
    else:
        # Backward compatibility: write to stdout
        print(json_str)
        sys.stdout.flush()


def read_phase_result(output_path: str) -> Dict[str, Any]:
    """
    Read phase result from a JSON file.

    Args:
        output_path: Path to the JSON result file

    Returns:
        Dictionary containing phase execution results

    Raises:
        FileNotFoundError: If output file doesn't exist
        json.JSONDecodeError: If file contains invalid JSON
    """
    output_file = Path(output_path)
    return json.loads(output_file.read_text(encoding='utf-8'))
