# Move-to-YML Learnings

Working file for incremental CI/CD rollout. Review this document before starting each subphase to avoid repeating mistakes and to reuse prior solutions.

## Guiding Principles
- Reuse caches aggressively (pip/venv, Whisper models, GH metadata) to keep workflow duration low.
- Prefer piping JSON inputs via stdin when a script expects stdin (e.g., `run_audio.py`) rather than adding new CLI options.
- Keep workflows in dry-run mode until downstream dependencies guarantee safe side-effects.
- Capture artifacts (logs + JSON output) even on failure to aid debugging.
- Update `OPERATIONS.md` and `phase4-tasklist.md` immediately after verifying a run.

## Phase 4.0 — CI Bootstrap
- Secrets checklist in `OPERATIONS.md` prevented missing-env run failures.
- Connectivity audit script should write report to predictable path (`ci-bootstrap-report.json`).
- Falling back to authenticated `gh` CLI avoids needing a token named `GITHUB_TOKEN` (GitHub disallows that secret name).

## Phase 4.1 — Discovery Workflow
- Use stdin/stdout JSON path, but discovery script already supports `--output`. Store output in `artifacts/discovery-output.json` for downstream phases.
- Pip/venv caches save several minutes on reruns; first-run heavy but subsequent runs faster.
- Dry-run mode still exercises DB access; ensure Supabase has recent data or discovery may return zero episodes.

## Phase 4.2 — Audio Workflow
- `run_audio.py` expects discovery JSON on stdin; pass file via shell redirection instead of nonexistent `--input` flag.
- Audio dry-run doesn’t produce transcripts, so downstream scoring must skip transcript existence checks when in dry-run.
- Apt install `ffmpeg` every run; acceptable but keep in mind for runtime budgeting.
- Whisper cache paths are empty during dry-run, causing cache-save warnings—documented as expected until real runs download models.

## TODO for Upcoming Phases
- Ensure scoring workflow reuses discovery output artifact (stdin) and that dry-run skips transcript checks (already patched).
- Keep artifact naming consistent (`scoring-phase`, `digest-phase`, etc.).
- Consider splitting discovery run into separate reusable composite action if repeated often.

Append new bullet points per subphase and adjust future workflows accordingly.
