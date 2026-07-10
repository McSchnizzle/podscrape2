#!/usr/bin/env python3
"""
Regression coverage for kanban #2709.

run_full_pipeline_orchestrator.py's run_pipeline() has always logged failures
loudly (see _log_failure) and returned {'success': False, ...}, but main()
discarded that return value instead of translating it into a process exit
code. With no unhandled exception, Python exits 0 regardless of outcome, so
the nightly cron wrapper's exit-code check (PIPESTATUS[0]) always saw success
even when a phase had failed. This test exercises main() with the heavy
PipelineOrchestrator construction/execution mocked out, and asserts the
process exit code follows the pipeline result.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import run_full_pipeline_orchestrator as orchestrator_module


@pytest.mark.parametrize(
    "pipeline_success,expected_exit_code",
    [
        (True, 0),
        (False, 1),
    ],
)
def test_main_exit_code_follows_pipeline_result(monkeypatch, pipeline_success, expected_exit_code):
    fake_orchestrator = MagicMock()
    fake_orchestrator.run_pipeline.return_value = {"success": pipeline_success}

    monkeypatch.setattr(
        orchestrator_module,
        "PipelineOrchestrator",
        MagicMock(return_value=fake_orchestrator),
    )
    monkeypatch.setattr(
        sys, "argv", ["run_full_pipeline_orchestrator.py", "--skip-audio", "--limit", "1"]
    )

    with pytest.raises(SystemExit) as exc_info:
        orchestrator_module.main()

    assert exc_info.value.code == expected_exit_code
    fake_orchestrator.run_pipeline.assert_called_once()
