"""
yt-dlp YouTube Transcript and Audio Fetcher

Provides fallback methods for YouTube content when the transcript API fails:
1. Subtitle download via yt-dlp (faster, no audio processing needed)
2. Audio download via yt-dlp (last resort, requires Whisper transcription)
"""

import logging
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from .subtitle_parser import parse_subtitle_file, ParsedSubtitle

logger = logging.getLogger(__name__)


@dataclass
class YtdlpTranscriptResult:
    """Result of a yt-dlp transcript/subtitle fetch."""
    video_id: str
    success: bool
    transcript_text: str = ""
    word_count: int = 0
    language: str = ""
    is_generated: bool = False
    error_message: str = ""
    fetch_time_seconds: float = 0.0


@dataclass
class YtdlpAudioResult:
    """Result of a yt-dlp audio download."""
    video_id: str
    success: bool
    audio_path: str = ""
    duration_seconds: float = 0.0
    error_message: str = ""
    fetch_time_seconds: float = 0.0


def _get_cookie_path() -> Optional[str]:
    """Check for YouTube cookies file for authenticated access."""
    possible_paths = [
        os.path.expanduser("~/.config/yt-dlp/cookies.txt"),
        os.path.expanduser("~/cookies.txt"),
        os.path.join(os.path.dirname(__file__), '..', '..', 'cookies.txt'),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            logger.debug(f"Found YouTube cookies at: {path}")
            return path
    return None


class YtdlpFetcher:
    """
    Fetches YouTube subtitles and audio using yt-dlp.
    More resilient to YouTube blocking than youtube-transcript-api.
    """

    def __init__(self, prefer_languages: List[str] = None):
        self.prefer_languages = prefer_languages or ['en', 'en-US', 'en-GB', 'en-AU']
        self.cookie_path = _get_cookie_path()
        if self.cookie_path:
            logger.info(f"yt-dlp will use cookies from: {self.cookie_path}")

    def _base_opts(self) -> dict:
        """Base yt-dlp options shared across methods."""
        opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
        }
        if self.cookie_path:
            opts['cookiefile'] = self.cookie_path
        return opts

    def fetch_subtitles(self, video_id: str) -> YtdlpTranscriptResult:
        """
        Fetch subtitles for a YouTube video using yt-dlp.
        Does NOT download the video - only extracts subtitle files.
        """
        if yt_dlp is None:
            return YtdlpTranscriptResult(
                video_id=video_id, success=False,
                error_message="yt-dlp not installed"
            )

        start_time = time.time()
        url = f"https://www.youtube.com/watch?v={video_id}"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_template = os.path.join(tmpdir, '%(id)s.%(ext)s')

            ydl_opts = {
                **self._base_opts(),
                'writeautomaticsub': True,
                'writesubtitles': True,
                'subtitleslangs': self.prefer_languages,
                'subtitlesformat': 'vtt',
                'skip_download': True,
                'outtmpl': output_template,
                'extract_flat': False,
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)

                    if not info:
                        return YtdlpTranscriptResult(
                            video_id=video_id, success=False,
                            error_message="Failed to extract video info",
                            fetch_time_seconds=time.time() - start_time
                        )

                    # Look for subtitle files
                    subtitle_files = list(Path(tmpdir).glob(f"{video_id}*.vtt"))
                    if not subtitle_files:
                        subtitle_files = [
                            f for f in Path(tmpdir).glob(f"{video_id}*.*")
                            if f.suffix in ['.vtt', '.srt', '.ttml']
                        ]

                    if not subtitle_files:
                        return YtdlpTranscriptResult(
                            video_id=video_id, success=False,
                            error_message="No subtitles available via yt-dlp",
                            fetch_time_seconds=time.time() - start_time
                        )

                    best_file = self._select_best_subtitle(subtitle_files)
                    parsed = parse_subtitle_file(str(best_file))

                    is_auto = '-orig' in best_file.name
                    lang_match = best_file.stem.replace(video_id, '').strip('.')
                    language = lang_match.split('-')[0] if lang_match else 'en'

                    logger.info(f"yt-dlp subtitles for {video_id}: {parsed.word_count} words, lang={language}")

                    return YtdlpTranscriptResult(
                        video_id=video_id, success=True,
                        transcript_text=parsed.text,
                        word_count=parsed.word_count,
                        language=language,
                        is_generated=is_auto,
                        fetch_time_seconds=time.time() - start_time
                    )

            except Exception as e:
                # Check if subtitles were downloaded despite error
                subtitle_files = list(Path(tmpdir).glob(f"{video_id}*.vtt"))
                if subtitle_files:
                    try:
                        best_file = self._select_best_subtitle(subtitle_files)
                        parsed = parse_subtitle_file(str(best_file))
                        if parsed.word_count > 0:
                            logger.info(f"yt-dlp got subtitles despite error for {video_id}: {parsed.word_count} words")
                            return YtdlpTranscriptResult(
                                video_id=video_id, success=True,
                                transcript_text=parsed.text,
                                word_count=parsed.word_count,
                                language='en', is_generated=True,
                                fetch_time_seconds=time.time() - start_time
                            )
                    except Exception:
                        pass

                error_msg = str(e)
                if 'HTTP Error 429' in error_msg:
                    error_msg = "Rate limited by YouTube (HTTP 429)"

                logger.error(f"yt-dlp subtitle fetch failed for {video_id}: {error_msg}")
                return YtdlpTranscriptResult(
                    video_id=video_id, success=False,
                    error_message=error_msg,
                    fetch_time_seconds=time.time() - start_time
                )

    def download_audio(self, video_id: str, output_dir: str) -> YtdlpAudioResult:
        """
        Download audio from a YouTube video using yt-dlp.
        Returns the path to the downloaded audio file.
        """
        if yt_dlp is None:
            return YtdlpAudioResult(
                video_id=video_id, success=False,
                error_message="yt-dlp not installed"
            )

        start_time = time.time()
        url = f"https://www.youtube.com/watch?v={video_id}"
        output_path = os.path.join(output_dir, f"{video_id}.mp3")

        ydl_opts = {
            **self._base_opts(),
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': os.path.join(output_dir, f'{video_id}.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',
            }],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

                if not info:
                    return YtdlpAudioResult(
                        video_id=video_id, success=False,
                        error_message="Failed to extract video info",
                        fetch_time_seconds=time.time() - start_time
                    )

                duration = info.get('duration', 0)

                # Find the output file (might have different extension)
                if os.path.exists(output_path):
                    audio_file = output_path
                else:
                    possible_files = list(Path(output_dir).glob(f"{video_id}.*"))
                    audio_files = [f for f in possible_files if f.suffix in ['.mp3', '.m4a', '.opus', '.webm']]
                    if audio_files:
                        audio_file = str(audio_files[0])
                    else:
                        return YtdlpAudioResult(
                            video_id=video_id, success=False,
                            error_message="Audio file not found after download",
                            fetch_time_seconds=time.time() - start_time
                        )

                file_size_mb = os.path.getsize(audio_file) / (1024 * 1024)
                logger.info(f"yt-dlp audio downloaded for {video_id}: {file_size_mb:.1f}MB, {duration}s")

                return YtdlpAudioResult(
                    video_id=video_id, success=True,
                    audio_path=audio_file,
                    duration_seconds=float(duration),
                    fetch_time_seconds=time.time() - start_time
                )

        except Exception as e:
            error_msg = str(e)
            if 'HTTP Error 429' in error_msg:
                error_msg = "Rate limited by YouTube (HTTP 429)"
            logger.error(f"yt-dlp audio download failed for {video_id}: {error_msg}")
            return YtdlpAudioResult(
                video_id=video_id, success=False,
                error_message=error_msg,
                fetch_time_seconds=time.time() - start_time
            )

    def _select_best_subtitle(self, subtitle_files: List[Path]) -> Path:
        """Select the best subtitle file (prefer English manual over auto-generated)."""
        scored_files = []
        for f in subtitle_files:
            score = 0
            name = f.name.lower()
            if '.en.' in name or '.en-' in name:
                score += 100
            if '-orig' not in name:
                score += 50
            if f.suffix == '.vtt':
                score += 10
            scored_files.append((score, f))
        scored_files.sort(key=lambda x: x[0], reverse=True)
        return scored_files[0][1]
