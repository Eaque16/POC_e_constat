import sys
from types import SimpleNamespace

from econstat.config import Settings
from econstat.schemas.claim import TranscriptSegment
from econstat.services.diarization import Diarizer, clear_diarization_cache
from econstat.services.role_assignment import assign_roles


def segment(start=0, end=2, text="Bonjour service sinistre"):
    return TranscriptSegment(start=start, end=end, text=text)


def test_missing_token_returns_explicit_unknown_fallback(tmp_path):
    settings = Settings(disable_auth=True, model_dir=tmp_path, hf_token=None)

    outcome = Diarizer(settings).run(tmp_path / "audio.wav")
    assigned = assign_roles([segment(text="bruit hésitation")], outcome.turns)

    assert outcome.available is False
    assert outcome.status == "fallback"
    assert outcome.reason == "hf_token_missing"
    assert assigned.segments[0].speaker == "INCONNU"
    assert assigned.heuristic_used is False


def test_token_does_not_authorize_implicit_download(tmp_path):
    settings = Settings(
        disable_auth=True,
        model_dir=tmp_path,
        hf_token="not-a-real-token",
        allow_model_downloads=False,
    )

    outcome = Diarizer(settings).run(tmp_path / "audio.wav")

    assert outcome.available is False
    assert outcome.reason == "local_model_missing_downloads_disabled"


def test_local_pipeline_is_cached_and_uses_pyannote_3_api(tmp_path, monkeypatch):
    model_dir = tmp_path / "models"
    config = model_dir / "pyannote" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("pipeline: synthetic", encoding="utf-8")
    calls = []

    class Turn:
        start = 0.0
        end = 2.0

    class Annotation:
        def itertracks(self, yield_label=False):
            assert yield_label is True
            return iter([(Turn(), None, "SPEAKER_00")])

    class FakeRuntime:
        def __call__(self, audio, num_speakers):
            assert num_speakers == 2
            assert str(audio).endswith("audio.wav")
            return Annotation()

    class FakePipeline:
        @classmethod
        def from_pretrained(cls, source, **kwargs):
            calls.append((source, kwargs))
            return FakeRuntime()

    monkeypatch.setitem(sys.modules, "pyannote.audio", SimpleNamespace(Pipeline=FakePipeline))
    clear_diarization_cache()
    settings = Settings(disable_auth=True, model_dir=model_dir, hf_token=None)

    first = Diarizer(settings).run(tmp_path / "audio.wav")
    second = Diarizer(settings).run(tmp_path / "audio.wav")

    assert first.available is True
    assert first.turns == [(0.0, 2.0, "SPEAKER_00")]
    assert second.available is True
    assert len(calls) == 1
    assert calls[0][1]["use_auth_token"] is None
    assert "token" not in calls[0][1]
    clear_diarization_cache()


def test_pyannote_runtime_failure_becomes_visible_fallback(tmp_path, monkeypatch):
    config = tmp_path / "pyannote" / "config.yaml"
    config.parent.mkdir()
    config.write_text("pipeline: synthetic", encoding="utf-8")

    class FakePipeline:
        @classmethod
        def from_pretrained(cls, *_args, **_kwargs):
            raise OSError("poids manquant")

    monkeypatch.setitem(sys.modules, "pyannote.audio", SimpleNamespace(Pipeline=FakePipeline))
    clear_diarization_cache()

    outcome = Diarizer(Settings(disable_auth=True, model_dir=tmp_path)).run(
        tmp_path / "audio.wav"
    )

    assert outcome.available is False
    assert outcome.reason == "pyannote_oserror"
    clear_diarization_cache()


def test_two_speakers_welcome_heuristic_is_explicit():
    segments = [
        segment(0, 2, "Bonjour service sinistre"),
        segment(2, 5, "Je viens déclarer un accident"),
    ]

    outcome = assign_roles(segments, [(0, 2, "S0"), (2, 5, "S1")])

    assert [item.speaker for item in outcome.segments] == ["AGENT", "ASSURE"]
    assert outcome.heuristic_used is True
    assert outcome.reason == "welcome_phrase"


def test_segment_without_overlap_remains_unknown():
    segments = [segment(0, 1), segment(5, 6, "parole hors tour")]

    outcome = assign_roles(segments, [(0, 1, "S0")])

    assert [item.speaker for item in outcome.segments] == ["AGENT", "INCONNU"]
