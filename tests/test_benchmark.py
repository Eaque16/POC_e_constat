import json
from pathlib import Path

from scripts.benchmark import (
    benchmark,
    diarization_error_rate,
    score_extraction,
    word_error_rate,
)


def test_wer_counts_substitution_insertion_and_deletion():
    result = word_error_rate("un deux trois", "un quatre trois cinq")

    assert result == {"errors": 2, "reference_words": 3, "wer": 0.666667}


def test_der_reports_confusion_and_missed_speech():
    result = diarization_error_rate(
        [
            {"start": 0, "end": 2, "speaker": "AGENT"},
            {"start": 2, "end": 4, "speaker": "ASSURE"},
        ],
        [
            {"start": 0, "end": 1, "speaker": "AGENT"},
            {"start": 1, "end": 2, "speaker": "ASSURE"},
            {"start": 2, "end": 3, "speaker": "ASSURE"},
        ],
    )

    assert result["confusion_seconds"] == 1
    assert result["missed_seconds"] == 1
    assert result["der"] == 0.5


def test_extraction_scores_missing_and_invented_values():
    result = score_extraction(
        [
            {"ground_truth": {"plaque": "AB 123 CI", "lieu": "Cocody"}},
            {"ground_truth": {}},
        ],
        [{"plaque": "AB 123 CI"}, {"lieu": "Plateau"}],
    )

    assert result["micro_precision"] == 0.5
    assert result["micro_recall"] == 0.5
    assert result["hallucination_rate"] == 0.5
    assert result["human_correction_case_rate"] == 1


def test_default_manifest_benchmark_is_traceable_and_offline(tmp_path):
    result = benchmark(
        manifest_path=Path("data/demo/benchmark_manifest.json"),
        profile="fast",
        run_asr_enabled=False,
    )
    output = tmp_path / "result.json"
    output.write_text(json.dumps(result), encoding="utf-8")

    assert result["dataset_version"] == "synthetic-text-v1"
    assert result["dataset_hash"]
    assert result["dependency_lock_hash"]
    assert result["git_commit"]
    assert isinstance(result["git_dirty"], bool)
    assert result["parameters"]["run_asr"] is False
    assert result["parameters"]["allow_model_downloads"] is False
    assert result["metrics"]["transcription"]["wer"] is None
    assert result["metrics"]["diarization"]["der"] is None
    assert result["metrics"]["extraction"]["micro_f1"] > 0
