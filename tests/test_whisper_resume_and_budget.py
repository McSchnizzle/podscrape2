"""Long Whisper transcriptions resume instead of restarting, and stop cleanly at the run budget.

2026-09-27: "Can Cloudflare save the web from AI?" (8 x 10-min chunks) was killed at the 2h cron
timeout three times during the day (~25 min/chunk under load) and restarted from chunk 1 each time;
it finished at 23:53, after the 21:05 digest. Finished chunks are now cached beside the audio
(`<chunk>.<chunk_seconds>s.txt`), and a run that reaches its time budget raises
TranscriptionDeferred BETWEEN chunks rather than being killed mid-chunk.
"""
import time
from pathlib import Path
from unittest import mock

import pytest

from src.podcast.openai_whisper_transcriber import (
    OpenAIWhisperTranscriber,
    TranscriptionChunk,
    TranscriptionDeferred,
)


class FakeRepo:
    def __init__(self):
        self.chunks = []

    def reset_transcript(self, guid):
        self.chunks = []

    def append_transcript_chunk(self, guid, text, n):
        self.chunks.append((n, text))
        return sum(len(t.split()) for _, t in self.chunks)

    def finalize_transcript(self, guid):
        pass


def _transcriber():
    t = OpenAIWhisperTranscriber.__new__(OpenAIWhisperTranscriber)
    t.chunk_duration_seconds = 600
    t._initialize_model = lambda: None
    return t


def _chunks(tmp_path, n):
    paths = []
    for i in range(1, n + 1):
        p = tmp_path / f"abc_chunk_{i:03d}.mp3"
        p.write_bytes(b"x")
        paths.append(str(p))
    return paths


def _fake_transcribe(calls):
    def f(chunk_path, chunk_number, start_time):
        calls.append(chunk_number)
        return TranscriptionChunk(chunk_number=chunk_number, start_time_seconds=start_time,
                                  end_time_seconds=start_time + 600, text=f"words of chunk {chunk_number}",
                                  confidence=1.0, processing_time_seconds=1500.0)
    return f


def test_deadline_defers_between_chunks_then_next_run_resumes_from_cache(tmp_path):
    chunks = _chunks(tmp_path, 4)
    repo = FakeRepo()
    t = _transcriber()
    calls = []
    t._transcribe_chunk = _fake_transcribe(calls)

    # Run 1: budget runs out after two chunks.
    # The clock passes the deadline once two chunks have been transcribed.
    with mock.patch("src.podcast.openai_whisper_transcriber.time.monotonic",
                    lambda: 0.0 if len(calls) < 2 else 9999.0):
        with pytest.raises(TranscriptionDeferred) as exc:
            t.transcribe_episode(chunks, "guid", episode_repo=repo, deadline_monotonic=100.0)
    assert (exc.value.chunks_done, exc.value.total_chunks) == (2, 4)
    assert calls == [1, 2]
    assert Path(f"{chunks[0]}.600s.txt").read_text() == "words of chunk 1"

    # Run 2: resumes -- chunks 1-2 from cache, only 3-4 transcribed, transcript rebuilt in order.
    calls.clear()
    result = t.transcribe_episode(chunks, "guid", episode_repo=repo, deadline_monotonic=time.monotonic() + 3600)
    assert calls == [3, 4]
    assert [n for n, _ in repo.chunks] == [1, 2, 3, 4]
    assert result.chunk_count == 4


def test_cached_chunks_are_used_even_past_the_deadline(tmp_path):
    chunks = _chunks(tmp_path, 2)
    for c in chunks:
        Path(f"{c}.600s.txt").write_text("cached text")
    t = _transcriber()
    calls = []
    t._transcribe_chunk = _fake_transcribe(calls)
    repo = FakeRepo()
    t.transcribe_episode(chunks, "guid", episode_repo=repo, deadline_monotonic=0.0)
    assert calls == []
    assert len(repo.chunks) == 2


def test_cache_from_a_different_chunk_length_is_ignored(tmp_path):
    chunks = _chunks(tmp_path, 1)
    Path(f"{chunks[0]}.180s.txt").write_text("text cut at 3-minute boundaries")
    Path(f"{chunks[0]}.txt").write_text("legacy unkeyed cache")
    t = _transcriber()
    calls = []
    t._transcribe_chunk = _fake_transcribe(calls)
    t.transcribe_episode(chunks, "guid", episode_repo=FakeRepo(), deadline_monotonic=None)
    assert calls == [1]


def test_deferral_is_not_wrapped_as_a_failure(tmp_path):
    chunks = _chunks(tmp_path, 1)
    t = _transcriber()
    t._transcribe_chunk = _fake_transcribe([])
    with pytest.raises(TranscriptionDeferred):
        t.transcribe_episode(chunks, "guid", episode_repo=FakeRepo(), deadline_monotonic=-1.0)
