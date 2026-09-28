"""Regression tests for resumable memory-efficient Whisper transcription."""

from unittest.mock import Mock, call

import pytest

from src.podcast.openai_whisper_transcriber import (
    OpenAIWhisperTranscriber,
    PodcastError,
)


def _audio_chunks(tmp_path, count):
    chunks = []
    for chunk_number in range(1, count + 1):
        chunk_path = tmp_path / f"chunk-{chunk_number}.mp3"
        chunk_path.write_bytes(b"audio" * 2048)
        chunks.append(str(chunk_path))
    return chunks


def _transcriber(model):
    transcriber = OpenAIWhisperTranscriber(chunk_duration_minutes=3)
    transcriber._whisper_model = model
    transcriber._initialized = True
    return transcriber


def _repo_with_transcript_state():
    repo = Mock()
    state = {"transcript": ""}

    def reset(_episode_guid):
        state["transcript"] = ""

    def append(_episode_guid, chunk_text, _chunk_number):
        state["transcript"] = " ".join(
            part for part in (state["transcript"], chunk_text) if part
        )
        return len(state["transcript"].split())

    repo.reset_transcript.side_effect = reset
    repo.append_transcript_chunk.side_effect = append
    return repo, state


def test_resume_reuses_cached_chunk_and_resets_once(tmp_path, caplog):
    chunks = _audio_chunks(tmp_path, 2)
    cached_text = "already transcribed first chunk"
    (tmp_path / "chunk-1.mp3.180s.txt").write_text(cached_text, encoding="utf-8")

    model = Mock()
    model.transcribe.return_value = {
        "text": "fresh second chunk",
        "segments": [{"end": 42.0}],
    }
    repo, state = _repo_with_transcript_state()

    with caplog.at_level("INFO"):
        result = _transcriber(model).transcribe_episode(
            chunks, "episode-guid", episode_repo=repo
        )

    model.transcribe.assert_called_once()
    assert model.transcribe.call_args.args[0] == chunks[1]
    repo.reset_transcript.assert_called_once_with("episode-guid")
    assert repo.append_transcript_chunk.call_args_list == [
        call("episode-guid", cached_text, 1),
        call("episode-guid", "fresh second chunk", 2),
    ]
    assert state["transcript"] == f"{cached_text} fresh second chunk"
    assert result.word_count == 7
    assert "reusing cached chunk 1" in caplog.text
    assert (
        tmp_path / "chunk-2.mp3.180s.txt"
    ).read_text(encoding="utf-8") == "fresh second chunk"


def test_rerun_after_kill_rebuilds_database_without_duplicates(tmp_path):
    chunks = _audio_chunks(tmp_path, 3)
    repo, state = _repo_with_transcript_state()

    first_model = Mock()
    first_model.transcribe.side_effect = [
        {"text": "first chunk", "segments": [{"end": 180.0}]},
        RuntimeError("worker killed"),
    ]

    with pytest.raises(PodcastError, match="worker killed"):
        _transcriber(first_model).transcribe_episode(
            chunks, "episode-guid", episode_repo=repo
        )

    assert state["transcript"] == "first chunk"
    assert (tmp_path / "chunk-1.mp3.180s.txt").read_text(encoding="utf-8") == "first chunk"
    assert not (tmp_path / "chunk-2.mp3.180s.txt").exists()

    repo.reset_mock()
    second_model = Mock()
    second_model.transcribe.side_effect = [
        {"text": "second chunk", "segments": [{"end": 180.0}]},
        {"text": "third chunk", "segments": [{"end": 75.0}]},
    ]

    _transcriber(second_model).transcribe_episode(
        chunks, "episode-guid", episode_repo=repo
    )

    repo.reset_transcript.assert_called_once_with("episode-guid")
    assert [entry.args[1] for entry in repo.append_transcript_chunk.call_args_list] == [
        "first chunk",
        "second chunk",
        "third chunk",
    ]
    assert state["transcript"] == "first chunk second chunk third chunk"
    assert state["transcript"].count("first chunk") == 1
    assert second_model.transcribe.call_count == 2
