import sys
from types import SimpleNamespace

import pytest

from econstat.config import Settings
from econstat.services.realtime_transcription import RealtimeTranscriber
from econstat.services.transcription import (
    Transcriber,
    TranscriptionError,
    clear_model_cache,
    normalise_logprob,
)


def create_model_directory(path):
    path.mkdir()
    for filename in ("config.json", "model.bin", "tokenizer.json"):
        (path / filename).write_bytes(b"synthetic")


def test_profile_selects_local_model_and_beam_size(tmp_path):
    fast = tmp_path / "fast"
    quality = tmp_path / "quality"
    settings = Settings(
        disable_auth=True,
        whisper_fast_model=str(fast),
        whisper_quality_model=str(quality),
        whisper_fast_beam_size=1,
        whisper_quality_beam_size=5,
    )

    assert Transcriber(settings, "fast").model_source == fast
    assert Transcriber(settings, "fast").beam_size == 1
    assert Transcriber(settings, "quality").model_source == quality
    assert Transcriber(settings, "quality").beam_size == 5
    with pytest.raises(TranscriptionError) as error:
        Transcriber(settings, "turbo")
    assert error.value.code == "whisper_profile_invalid"


def test_realtime_modes_select_tiny_or_small_without_download(tmp_path):
    tiny = tmp_path / "tiny"
    small = tmp_path / "small"
    settings = Settings(
        disable_auth=True,
        whisper_fast_model=str(tiny),
        whisper_small_model=str(small),
    )

    fast = RealtimeTranscriber(settings, "fast")
    precision = RealtimeTranscriber(settings, "precision")

    assert fast._transcriber.model_source == tiny
    assert precision._transcriber.model_source == small
    assert fast._transcriber.beam_size == 1
    assert precision._transcriber.beam_size == 1
    with pytest.raises(ValueError, match="Mode ASR interactif inconnu"):
        RealtimeTranscriber(settings, "quality")


def test_incomplete_model_fails_without_downloading(tmp_path):
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    settings = Settings(disable_auth=True, whisper_fast_model=str(incomplete))
    transcriber = Transcriber(settings, "fast")

    with pytest.raises(TranscriptionError) as error:
        transcriber._load()

    assert error.value.code == "whisper_model_incomplete"
    assert "model.bin" in str(error.value)


def test_transcription_segments_trace_and_process_cache(tmp_path, monkeypatch):
    model_dir = tmp_path / "model"
    create_model_directory(model_dir)
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"synthetic")
    created = []

    class FakeSegment:
        start = 0.2
        end = 1.4
        text = " bonjour "
        avg_logprob = -0.2

    class FakeModel:
        def __init__(self, *args, **kwargs):
            created.append((args, kwargs))

        def transcribe(self, *_args, **_kwargs):
            return iter([FakeSegment()]), SimpleNamespace(duration=2.0)

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeModel))
    clear_model_cache()
    settings = Settings(
        disable_auth=True,
        whisper_fast_model=str(model_dir),
        whisper_device="cpu",
        whisper_compute_type="int8",
    )

    first = Transcriber(settings, "fast")
    second = Transcriber(settings, "fast")
    first_segments = first.transcribe(audio)
    second.transcribe(audio)

    assert len(created) == 1
    assert created[0][1]["local_files_only"] is True
    assert first_segments[0].text == "bonjour"
    assert first_segments[0].confidence == normalise_logprob(-0.2)
    assert first.last_trace.device == "cpu"
    assert first.last_trace.compute_type == "int8"
    assert first.last_trace.audio_duration_seconds == 2.0
    assert first.last_trace.realtime_factor is not None
    assert "non calibré métier" in first.last_trace.confidence_method
    clear_model_cache()


@pytest.mark.parametrize(
    ("value", "expected"),
    [(-1.0, 0.3679), (0.0, 1.0), (10.0, 1.0), (float("nan"), 0.0)],
)
def test_confidence_indicator_is_bounded(value, expected):
    assert normalise_logprob(value) == expected
