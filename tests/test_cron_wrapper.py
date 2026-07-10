#!/usr/bin/env python3
"""
Regression coverage for scripts/run_pipeline_with_alerts.sh (kanban #2709).

The wrapper is invoked directly by cron/patrol with no real pipeline run, no
network access, and never touching the real /home/pbrown/logs/podcast-cron.log
or store/ state. It drives the real wrapper script (symlinked into a throwaway
project directory so the script's own $0-derived PROJECT_DIR resolution points
there) against a stubbed run_full_pipeline_orchestrator.py whose exit code is
controlled by an env var, exercising both the failure and success paths.
"""
import os
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
WRAPPER = REPO_ROOT / "scripts" / "run_pipeline_with_alerts.sh"

STUB_ORCHESTRATOR = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import os, sys
    code = int(os.environ.get("PIPELINE_STUB_EXIT_CODE", "0"))
    print("STUB PIPELINE FAILED" if code else "STUB PIPELINE OK")
    sys.exit(code)
    """
)


@pytest.fixture
def fake_project(tmp_path):
    """A throwaway project dir shaped like the real one: scripts/ holds a
    symlink to the real wrapper (so its $0-derived PROJECT_DIR resolves to
    tmp_path), plus a no-op .env / venv activate and a stubbed pipeline
    entrypoint standing in for run_full_pipeline_orchestrator.py."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "run_pipeline_with_alerts.sh").symlink_to(WRAPPER)

    (tmp_path / ".env").write_text("")

    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "activate").write_text("# stub venv activate, no-op\n")

    orchestrator = tmp_path / "run_full_pipeline_orchestrator.py"
    orchestrator.write_text(STUB_ORCHESTRATOR)
    orchestrator.chmod(orchestrator.stat().st_mode | stat.S_IEXEC)

    return tmp_path


def _run_wrapper(fake_project, tmp_path, stub_exit_code):
    log_file = tmp_path / "cron.log"
    env = dict(os.environ)
    env["PIPELINE_STUB_EXIT_CODE"] = str(stub_exit_code)
    env["LOG_FILE"] = str(log_file)
    result = subprocess.run(
        ["bash", str(fake_project / "scripts" / "run_pipeline_with_alerts.sh")],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    log_contents = log_file.read_text() if log_file.exists() else ""
    return result, log_contents


def test_failing_phase_is_reported_as_failure(fake_project, tmp_path):
    result, log_contents = _run_wrapper(fake_project, tmp_path, stub_exit_code=1)

    assert result.returncode != 0, "wrapper must exit non-zero when a phase fails"
    assert "Pipeline completed successfully" not in log_contents
    assert "Pipeline FAILED" in log_contents


def test_successful_run_logs_success_exactly_once(fake_project, tmp_path):
    result, log_contents = _run_wrapper(fake_project, tmp_path, stub_exit_code=0)

    assert result.returncode == 0
    assert log_contents.count("Pipeline completed successfully") == 1
    assert "Pipeline FAILED" not in log_contents
