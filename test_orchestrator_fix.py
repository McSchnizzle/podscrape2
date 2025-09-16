#!/usr/bin/env python3
"""
Test if the database connection fix resolves the FFmpeg hanging issue
in the orchestrator execution chain.
"""

import subprocess
import sys
import time
from pathlib import Path

def test_audio_script_direct():
    """Test running the audio script directly with the improved connection management"""

    print("Testing audio script with database connection fixes...")

    # Use the episode that was failing - create a minimal JSON input
    test_input = {
        "success": True,
        "episodes": [{
            "guid": "f9e01234-5678-90ab-cdef-123456789abc",  # Use the failing episode GUID
            "title": "Welcome to Law School 2025",
            "mode": "resume"
        }]
    }

    import json

    cmd = [
        sys.executable,
        'scripts/run_audio.py',
        '--verbose',
        '--limit', '1',
        '--dry-run'  # Use dry run to avoid actual processing
    ]

    log_file = Path("test_audio_fix.log")

    print(f"Running: {' '.join(cmd)}")

    start_time = time.time()

    try:
        with open(log_file, 'w') as f:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=f,
                stderr=f,
                text=True
            )

            # Send the test input
            process.stdin.write(json.dumps(test_input))
            process.stdin.close()

            # Wait with timeout
            return_code = process.wait(timeout=60)  # 1 minute should be enough for dry run

            elapsed = time.time() - start_time
            print(f"Audio script completed in {elapsed:.1f}s with return code: {return_code}")

            # Show output
            print("\n--- Audio script output ---")
            with open(log_file, 'r') as rf:
                output = rf.read()
                print(output)

            return return_code == 0

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print(f"❌ Audio script timed out after {elapsed:.1f}s")
        process.kill()
        process.wait()

        # Show partial output
        print("\n--- Partial output before timeout ---")
        with open(log_file, 'r') as rf:
            print(rf.read())

        return False

    except Exception as e:
        print(f"❌ Error running audio script: {e}")
        return False

if __name__ == "__main__":
    success = test_audio_script_direct()
    if success:
        print("✅ Audio script test passed - database connection fix appears to work")
    else:
        print("❌ Audio script test failed - may need additional fixes")

    sys.exit(0 if success else 1)