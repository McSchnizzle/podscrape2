#!/usr/bin/env python3
"""Utility to simulate TTS output by writing placeholder MP3 files.

This avoids external ElevenLabs API calls while letting CI exercises verify
file persistence and artifact uploads. When FFmpeg is available the script
synthesises a longer sine-wave sample so downstream systems can validate large
asset handling; otherwise it falls back to a small embedded MP3 sample.
"""

import argparse
import base64
import datetime as dt
import logging
import shutil
import subprocess
from pathlib import Path
from typing import List

logger = logging.getLogger("simulate_tts")
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

_FALLBACK_MP3_BASE64 = """\
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
VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX/+4DE+YAIQFcn9eEAJC2xJb89oAhV
VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV
VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV
VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV
VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV
VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV
VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV
Vf/7EMTag8EUCxEcMAAoAAA0gAAABFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV
VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV
""".strip()


def _sanitize_stem(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)


def _generate_with_ffmpeg(output_path: Path, duration: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        'ffmpeg',
        '-hide_banner',
        '-loglevel', 'error',
        '-f', 'lavfi',
        '-i', f'sine=frequency=440:duration={duration}',
        '-q:a', '2',
        str(output_path)
    ]
    subprocess.run(cmd, check=True)


def _generate_from_base64(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(base64.b64decode(_FALLBACK_MP3_BASE64))


def _generate_mp3(output_path: Path, duration: int) -> str:
    if duration <= 0:
        duration = 1
    if shutil.which('ffmpeg'):
        try:
            _generate_with_ffmpeg(output_path, duration)
            return 'ffmpeg'
        except subprocess.CalledProcessError as exc:
            logger.warning("FFmpeg generation failed (%s). Falling back to embedded sample.", exc)
    _generate_from_base64(output_path)
    return 'embedded sample'


def simulate(topics: List[str], output_dir: Path, timestamp: str | None, duration: int) -> List[Path]:
    created: List[Path] = []
    ts = timestamp or dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d_%H%M%S')

    for idx, topic in enumerate(topics, start=1):
        stem = f"{_sanitize_stem(topic)}_{ts}_{idx:02d}"
        output_path = output_dir / f"{stem}.mp3"
        method = _generate_mp3(output_path, duration)
        size = output_path.stat().st_size
        logger.info("Wrote placeholder MP3 via %s: %s (%d bytes)", method, output_path, size)
        created.append(output_path)

    return created


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate TTS MP3 generation")
    parser.add_argument(
        "--topics",
        nargs="*",
        default=["Simulated Digest"],
        help="Topic names to encode into the MP3 filenames",
    )
    parser.add_argument(
        "--output-dir",
        default=Path("data/completed-tts/current"),
        type=Path,
        help="Directory where placeholder MP3s will be written",
    )
    parser.add_argument(
        "--timestamp",
        default=None,
        help="Optional timestamp to embed in filenames (UTC YYYYmmdd_HHMMSS)",
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=300,
        help="Duration of synthetic audio in seconds when FFmpeg is available (default: 300)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    created = simulate(args.topics, args.output_dir, args.timestamp, args.duration_seconds)

    logger.info("Generated %d placeholder MP3 file(s)", len(created))
    for path in created:
        logger.info(" -> %s", path)


if __name__ == "__main__":
    main()
