#!/usr/bin/env python3
"""
Test FFmpeg chunking within a subprocess to mimic Web UI behavior
"""

import subprocess
import sys
from pathlib import Path

def run_ffmpeg_test():
    """Test running the ffmpeg chunking within a subprocess like the Web UI does"""

    # This mimics how the Web UI calls the orchestrator
    cmd = [
        sys.executable, '-c', '''
import sys
sys.path.append("src")

from src.podcast.audio_processor import AudioProcessor
from src.utils.logging_config import setup_logging
from pathlib import Path

setup_logging()
processor = AudioProcessor(chunk_duration_minutes=5)

audio_cache = Path("audio_cache")
if audio_cache.exists():
    audio_files = list(audio_cache.glob("*.mp3"))
    if audio_files:
        test_file = audio_files[0]
        print(f"Testing with subprocess: {test_file}")
        try:
            chunks = processor.chunk_audio(str(test_file), "subprocess-test-guid")
            print(f"SUCCESS: Created {len(chunks)} chunks via subprocess")
        except Exception as e:
            print(f"FAILED: {e}")
    else:
        print("No audio files found")
else:
    print("No audio_cache directory")
'''
    ]

    # Run with output to file like Web UI does
    log_file = Path("test_subprocess_ffmpeg.log")

    print("Running FFmpeg test via subprocess (like Web UI)...")
    with open(log_file, 'w') as f:
        process = subprocess.Popen(
            cmd,
            stdout=f,
            stderr=f,
            cwd=str(Path.cwd()),
            env=None  # Use current environment
        )

        # Wait with timeout
        try:
            return_code = process.wait(timeout=400)  # 6+ minute timeout
            print(f"Subprocess completed with return code: {return_code}")

            # Show the output
            print("\n--- Subprocess output ---")
            with open(log_file, 'r') as rf:
                print(rf.read())

        except subprocess.TimeoutExpired:
            print("⏰ Subprocess timed out! This reproduces the Web UI issue.")
            process.kill()
            process.wait()

            # Show partial output
            print("\n--- Partial output before timeout ---")
            with open(log_file, 'r') as rf:
                print(rf.read())

if __name__ == "__main__":
    run_ffmpeg_test()