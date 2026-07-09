"""Kanban #2709: a failed pipeline run must be reported as a failure.

On 2026-07-07 21:00 the digest phase failed hard and the orchestrator logged
'PIPELINE FAILED after 0:00:03', yet the cron wrapper appended 'Pipeline
completed successfully' -- because main() discarded run_pipeline()'s summary
and _log_failure RETURNS a failure dict instead of raising, so the process
exited 0. These tests pin both layers:

  - AC1 (orchestrator): main() exits non-zero when run_pipeline reports
    failure, and exits cleanly on success.
  - AC1 (wrapper): a 'PIPELINE FAILED' marker in the run output forces a
    failure result even if the process exit code lies (belt-and-suspenders,
    exercised by running the real wrapper script against a stub pipeline).
  - AC2 (wrapper): a successful run logs the success line exactly once.
"""

import os
import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import run_full_pipeline_orchestrator as orch  # noqa: E402


# ---------------------------------------------------------------------------
# Orchestrator exit code (root cause)
# ---------------------------------------------------------------------------

def _run_main_with_summary(summary):
    with patch.object(orch, 'PipelineOrchestrator') as fake_cls:
        fake_cls.return_value.run_pipeline.return_value = summary
        with patch.object(sys, 'argv', ['run_full_pipeline_orchestrator.py']):
            orch.main()


def test_main_exits_nonzero_when_pipeline_reports_failure():
    with pytest.raises(SystemExit) as exc:
        _run_main_with_summary({'success': False, 'error': 'digest phase failed'})
    assert exc.value.code == 1


def test_main_exits_nonzero_when_pipeline_returns_nothing():
    with pytest.raises(SystemExit) as exc:
        _run_main_with_summary(None)
    assert exc.value.code == 1


def test_main_returns_cleanly_on_success():
    _run_main_with_summary({'success': True})  # must not raise SystemExit


# ---------------------------------------------------------------------------
# Wrapper failure-marker guard (belt-and-suspenders) -- runs the REAL script
# against a stubbed pipeline entrypoint in a sandbox project dir.
# ---------------------------------------------------------------------------

WRAPPER = PROJECT_ROOT / 'scripts' / 'run_pipeline_with_alerts.sh'


def _run_wrapper(tmp_path: Path, stub_body: str) -> tuple[int, str]:
    """Run the real wrapper in a sandboxed copy of the project layout whose
    run_full_pipeline_orchestrator.py is a stub with the given behavior.
    Returns (exit_code, cron_log_text)."""
    proj = tmp_path / 'proj'
    (proj / 'scripts').mkdir(parents=True)
    (proj / '.venv' / 'bin').mkdir(parents=True)
    # Stub venv activate + env file the wrapper sources.
    (proj / '.venv' / 'bin' / 'activate').write_text('')
    (proj / '.env').write_text('')
    # notify_failure.py stub (failure path invokes it; never send real mail).
    (proj / 'scripts' / 'notify_failure.py').write_text('import sys\n')
    # Pipeline stub: the wrapper invokes `python3 run_full_pipeline_orchestrator.py ...`.
    (proj / 'run_full_pipeline_orchestrator.py').write_text(stub_body)
    # Copy the REAL wrapper, redirect its log into the sandbox.
    body = WRAPPER.read_text().replace(
        'LOG_FILE="/home/pbrown/logs/podcast-cron.log"',
        f'LOG_FILE="{proj}/cron.log"',
    )
    wrapper = proj / 'scripts' / 'run_pipeline_with_alerts.sh'
    wrapper.write_text(body)
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    (proj / 'cron.log').write_text('')
    res = subprocess.run(
        ['bash', str(wrapper)], cwd=str(proj), capture_output=True, text=True,
        env={**os.environ, 'HOME': str(tmp_path)}, timeout=60,
    )
    return res.returncode, (proj / 'cron.log').read_text()


def test_wrapper_failure_marker_beats_lying_exit_zero(tmp_path):
    rc, log = _run_wrapper(
        tmp_path,
        'print("PIPELINE FAILED after 0:00:03")\n',  # exits 0 -- the 07-07 lie
    )
    assert rc != 0
    assert 'completed successfully' not in log
    assert 'treating as failure' in log


def test_wrapper_success_logs_success_line_exactly_once(tmp_path):
    rc, log = _run_wrapper(
        tmp_path,
        'print("Pipeline orchestration completed successfully!")\n',
    )
    assert rc == 0
    assert log.count('Pipeline completed successfully') == 1


def test_wrapper_nonzero_exit_logs_failure(tmp_path):
    rc, log = _run_wrapper(
        tmp_path,
        'import sys\nprint("boom")\nsys.exit(3)\n',
    )
    assert rc == 3
    assert 'Pipeline FAILED with exit code 3' in log
    assert 'completed successfully' not in log
