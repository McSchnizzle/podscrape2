#!/usr/bin/env python3
"""
Pre-deploy smoke test for critical code paths.

Run this BEFORE deploying to et01 to catch breaking changes early.
Tests the Anthropic streaming path, yt-dlp availability, and basic pipeline imports.

Usage:
    python3 scripts/smoke_test_deploy.py
"""

import os
import sys
import time

# Ensure project root is on sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"


def test_claude_p():
    """Test that claude -p (programmatic mode) works for LLM calls.

    This replaces the previous Anthropic API streaming tests. claude -p runs
    on the Claude subscription instead of per-token API billing.
    """

    # ┌─────────────────────────────────────────────────────────────────────┐
    # │ PREVIOUS IMPLEMENTATION: Two Anthropic API streaming tests          │
    # │ To revert: restore test_anthropic_streaming() and                   │
    # │ test_anthropic_large_max_tokens(), update main() test list,         │
    # │ and restore 'import anthropic' in each function.                    │
    # │                                                                     │
    # │ def test_anthropic_streaming():                                     │
    # │     client = anthropic.Anthropic(api_key=os.environ['...'])         │
    # │     with client.messages.stream(model="claude-sonnet-4-6",          │
    # │         max_tokens=100, system="...", messages=[...]) as stream:    │
    # │         for text in stream.text_stream: output_text += text         │
    # │                                                                     │
    # │ def test_anthropic_large_max_tokens():                              │
    # │     # Same pattern with max_tokens=25000 to test timeout guard      │
    # └─────────────────────────────────────────────────────────────────────┘

    import subprocess

    claude_path = os.path.expanduser("~/.local/bin/claude")
    if not os.path.exists(claude_path):
        claude_path = "claude"

    try:
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)

        result = subprocess.run(
            [claude_path, "-p", "-"],
            input="Respond with exactly: SMOKE_TEST_OK",
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )

        if result.returncode != 0:
            return FAIL, f"claude -p exited {result.returncode}: {result.stderr[:200]}"

        output_text = result.stdout.strip()
        if "SMOKE_TEST_OK" in output_text:
            return PASS, f"claude -p works, got expected response ({len(output_text)} chars)"
        else:
            return PASS, f"claude -p works, got: {output_text[:50]}"

    except FileNotFoundError:
        return FAIL, f"claude CLI not found at {claude_path}"
    except subprocess.TimeoutExpired:
        return FAIL, "claude -p timed out after 60s"
    except Exception as e:
        return FAIL, f"claude -p failed: {e}"


def test_ytdlp_available():
    """Test that yt-dlp is importable."""
    try:
        import yt_dlp
        return PASS, f"yt-dlp version: {yt_dlp.version.__version__}"
    except ImportError:
        return FAIL, "yt-dlp not installed (pip3 install yt-dlp)"


def test_script_generator_import():
    """Test that the script generator imports without errors."""
    try:
        from src.generation.script_generator import ScriptGenerator
        return PASS, "ScriptGenerator imports OK"
    except Exception as e:
        return FAIL, f"Import failed: {e}"


def test_youtube_modules_import():
    """Test that YouTube modules import correctly."""
    try:
        from src.youtube.transcript_processor import TranscriptProcessor
        from src.youtube.ytdlp_fetcher import YtdlpFetcher
        from src.youtube.subtitle_parser import parse_vtt
        return PASS, "All YouTube modules import OK"
    except Exception as e:
        return FAIL, f"YouTube module import failed: {e}"


def test_audio_phase_import():
    """Test that the audio phase script imports without errors."""
    try:
        # Just verify the file is syntactically valid
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_audio",
            os.path.join(project_root, "scripts", "run_audio.py")
        )
        mod = importlib.util.module_from_spec(spec)
        # Don't actually execute - just verify it parses
        import ast
        with open(os.path.join(project_root, "scripts", "run_audio.py")) as f:
            ast.parse(f.read())
        return PASS, "run_audio.py parses OK"
    except SyntaxError as e:
        return FAIL, f"Syntax error in run_audio.py: {e}"
    except Exception as e:
        return FAIL, f"Error checking run_audio.py: {e}"


def main():
    tests = [
        ("claude -p (LLM calls)", test_claude_p),
        ("yt-dlp available", test_ytdlp_available),
        ("Script generator import", test_script_generator_import),
        ("YouTube modules import", test_youtube_modules_import),
        ("Audio phase syntax", test_audio_phase_import),
    ]

    print("=" * 60)
    print("PRE-DEPLOY SMOKE TEST")
    print("=" * 60)

    results = []
    for name, test_fn in tests:
        print(f"\n  Testing: {name}...", end=" ", flush=True)
        start = time.time()
        status, detail = test_fn()
        elapsed = time.time() - start
        results.append((name, status, detail))
        print(f"[{status}] ({elapsed:.1f}s)")
        if detail:
            print(f"    {detail}")

    print("\n" + "=" * 60)
    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    skipped = sum(1 for _, s, _ in results if s == SKIP)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")

    if failed > 0:
        print("\n*** DEPLOY BLOCKED: Fix failures before deploying to et01 ***")
        sys.exit(1)
    else:
        print("\n*** All checks passed - safe to deploy ***")
        sys.exit(0)


if __name__ == "__main__":
    main()
