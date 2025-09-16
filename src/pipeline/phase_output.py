#!/usr/bin/env python3
"""
Phase Output Module - Unified JSON output reporting for pipeline phases
Provides consistent JSON output structure and separation between human-readable and machine output.
"""

import json
import sys
import logging
from typing import Dict, Any, Optional


def report_phase_result(
    phase_name: str,
    success: bool,
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    json_mode: bool = False
) -> int:
    """
    Unified phase result reporting for pipeline orchestration

    Args:
        phase_name: Name of the pipeline phase (e.g., 'audio', 'scoring')
        success: Whether the phase completed successfully
        error: Error message if phase failed
        metadata: Additional data to include in JSON output
        json_mode: Whether to output JSON to stdout for orchestrator

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger = logging.getLogger(__name__)

    if json_mode:
        # Create JSON result for orchestrator
        result = {
            'success': success,
            'phase': phase_name,
            'message': f'{phase_name.title()} phase completed successfully' if success else f'{phase_name.title()} phase failed'
        }

        if error:
            result['error'] = str(error)

        if metadata:
            result.update(metadata)

        # Output JSON to stdout (orchestrator reads this)
        try:
            print(json.dumps(result), flush=True)
            sys.stdout.flush()
        except Exception as e:
            logger.warning(f"Failed to output JSON result: {e}")

        logger.debug(f"JSON output generated for {phase_name} phase: success={success}")

    return 0 if success else 1


def should_output_json(args) -> bool:
    """
    Determine if script should output JSON based on arguments

    Args:
        args: Parsed command line arguments

    Returns:
        True if JSON output should be generated
    """
    # Output JSON if explicitly requested or if being called by orchestrator
    return getattr(args, 'json_output', False) or getattr(args, 'orchestrator_mode', False)


def setup_phase_logging(phase_name: str, script_version: str = "1.0") -> logging.Logger:
    """
    Setup consistent logging for phase scripts

    Args:
        phase_name: Name of the phase for logging
        script_version: Version of the script

    Returns:
        Configured logger
    """
    logger = logging.getLogger(__name__)

    # Log phase identification (goes to stderr via logging, not stdout)
    logger.info(f"🔧 PHASE SCRIPT: run_{phase_name}.py v{script_version} - Independent execution")

    phase_descriptions = {
        'discovery': '🔍 Discovery Phase - RSS Feed Discovery and Episode Identification',
        'audio': '🎧 Audio Processing Phase - Download and Transcription',
        'scoring': '🎯 Content Scoring Phase - AI-powered topic relevance scoring',
        'digest': '📝 Digest Generation Phase - Script Creation for Qualifying Topics',
        'tts': '🎤 TTS Phase - Text-to-Speech Audio Generation'
    }

    description = phase_descriptions.get(phase_name, f'{phase_name.title()} Phase')
    logger.info(description)

    return logger


def add_json_output_arg(parser):
    """
    Add standard JSON output argument to argument parser

    Args:
        parser: ArgumentParser to add argument to
    """
    parser.add_argument(
        '--json-output',
        action='store_true',
        help='Output JSON result for orchestrator compatibility'
    )