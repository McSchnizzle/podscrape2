The orchestrator still instantiates the retention manager on every run, which immediately runs the GitHub publisher validation path; on hosts without an authenticated gh CLI (e.g., the forthcoming hosted UI workers), this produces warnings or hard failures even for dry runs, so the initialization should be deferred or made optional before Phase 5.

run_phase_script detects results by assuming the phase scripts emit a single-line JSON blob; any future change to multi-line output or JSON-like log lines will be misparsed or ignored, which is risky as the Web UI evolves to consume richer status payloads.

There are minor redundancies in the orchestrator (unused logging/tempfile imports and the duplicated limit handling) that can be trimmed to keep the entry point lean before porting it into web-triggered contexts.

The publishing workflow re-implements every pipeline phase with shell string assembly and eval, so workflow inputs can break quoting and any CLI change must be updated in two places; the digest/TTS steps also ignore the dispatched limit, and the final artifact mixes logs with JSON because --verbose output is redirected alongside the result.

Secret validation in the workflow skips ELEVENLABS_API_KEY, allowing TTS dry runs to proceed without a credential—something Phase 5 will need once audio generation becomes real instead of mocked.

Automated coverage only checks that the orchestrator prints --help, while broader CLI suites remain skipped; combined with the environment gate that exits pytest when secrets are absent, we have no automated signal that the orchestrator or publishing flow actually work end-to-end yet.