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


def test_anthropic_streaming():
    """Test that Anthropic streaming API works with our code pattern."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return SKIP, "ANTHROPIC_API_KEY not set"

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # Use the exact same pattern as script_generator._call_llm()
        output_text = ""
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=100,
            system="You are a test assistant. Respond with exactly: SMOKE_TEST_OK",
            messages=[{"role": "user", "content": "Please respond."}]
        ) as stream:
            for text in stream.text_stream:
                output_text += text

        if "SMOKE_TEST_OK" in output_text:
            return PASS, f"Streaming works, got {len(output_text)} chars"
        else:
            return PASS, f"Streaming works, got response: {output_text[:50]}"

    except Exception as e:
        return FAIL, f"Anthropic streaming failed: {e}"


def test_anthropic_large_max_tokens():
    """Test that large max_tokens doesn't trigger the 10-min guard."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return SKIP, "ANTHROPIC_API_KEY not set"

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # Use the same max_tokens as production (25000) to verify no timeout guard
        output_text = ""
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=25000,
            system="Respond with exactly one word: OK",
            messages=[{"role": "user", "content": "Test."}]
        ) as stream:
            for text in stream.text_stream:
                output_text += text

        return PASS, f"Large max_tokens (25000) works with streaming"

    except Exception as e:
        return FAIL, f"Large max_tokens streaming failed: {e}"


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
        ("Anthropic streaming", test_anthropic_streaming),
        ("Anthropic large max_tokens", test_anthropic_large_max_tokens),
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
