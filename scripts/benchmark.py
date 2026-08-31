"""Benchmark reproductible, hors réseau par défaut, du POC E-Constat IA."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import tracemalloc
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from econstat.config import Settings  # noqa: E402
from econstat.services.extraction_rules import extract_rules  # noqa: E402
from econstat.services.lexicon import LocalLexicon  # noqa: E402

TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(path: Path | None) -> str | None:
    if path is None or not path.is_dir():
        return None
    digest = hashlib.sha256()
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(str(file_path.relative_to(path)).encode())
        digest.update(sha256_file(file_path).encode())
    return digest.hexdigest()


def normalise_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False, sort_keys=True).casefold()
    return " ".join(str(value).casefold().split())


def word_error_rate(reference: str, hypothesis: str) -> dict[str, float | int | None]:
    expected = TOKEN_PATTERN.findall(reference.casefold())
    actual = TOKEN_PATTERN.findall(hypothesis.casefold())
    previous = list(range(len(actual) + 1))
    for row, expected_word in enumerate(expected, 1):
        current = [row]
        for column, actual_word in enumerate(actual, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (expected_word != actual_word),
                )
            )
        previous = current
    errors = previous[-1]
    return {
        "errors": errors,
        "reference_words": len(expected),
        "wer": round(errors / len(expected), 6) if expected else None,
    }


def diarization_error_rate(reference: list[dict], hypothesis: list[dict]) -> dict:
    boundaries = sorted(
        {float(turn[edge]) for turn in [*reference, *hypothesis] for edge in ("start", "end")}
    )

    def speaker_at(turns: list[dict], moment: float) -> str | None:
        return next(
            (
                str(turn["speaker"])
                for turn in turns
                if float(turn["start"]) <= moment < float(turn["end"])
            ),
            None,
        )

    missed = false_alarm = confusion = reference_seconds = 0.0
    for start, end in zip(boundaries, boundaries[1:], strict=False):
        duration = end - start
        reference_speaker = speaker_at(reference, (start + end) / 2)
        hypothesis_speaker = speaker_at(hypothesis, (start + end) / 2)
        if reference_speaker:
            reference_seconds += duration
            if hypothesis_speaker is None:
                missed += duration
            elif hypothesis_speaker != reference_speaker:
                confusion += duration
        elif hypothesis_speaker:
            false_alarm += duration
    total_error = missed + false_alarm + confusion
    return {
        "der": round(total_error / reference_seconds, 6) if reference_seconds else None,
        "reference_seconds": round(reference_seconds, 6),
        "missed_seconds": round(missed, 6),
        "false_alarm_seconds": round(false_alarm, 6),
        "confusion_seconds": round(confusion, 6),
    }


def score_extraction(cases: list[dict], predictions: list[dict]) -> dict:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    invented = predicted_values = corrected_cases = 0
    for case, prediction in zip(cases, predictions, strict=True):
        truth = case.get("ground_truth", {})
        needs_correction = False
        for field in set(truth) | set(prediction):
            expected = normalise_text(truth.get(field))
            actual = normalise_text(prediction.get(field))
            if expected and actual and expected == actual:
                counts[field]["tp"] += 1
            else:
                if actual:
                    counts[field]["fp"] += 1
                    predicted_values += 1
                    if not expected:
                        invented += 1
                if expected:
                    counts[field]["fn"] += 1
                if expected != actual:
                    needs_correction = True
            if expected and actual and expected == actual:
                predicted_values += 1
        corrected_cases += int(needs_correction)

    per_field = {}
    field_f1 = []
    total = {"tp": 0, "fp": 0, "fn": 0}
    for field, values in sorted(counts.items()):
        precision = (
            values["tp"] / (values["tp"] + values["fp"]) if values["tp"] + values["fp"] else 0
        )
        recall = values["tp"] / (values["tp"] + values["fn"]) if values["tp"] + values["fn"] else 0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
        per_field[field] = {
            **values,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
        }
        field_f1.append(f1)
        for name in total:
            total[name] += values[name]
    micro_precision = total["tp"] / (total["tp"] + total["fp"]) if total["tp"] + total["fp"] else 0
    micro_recall = total["tp"] / (total["tp"] + total["fn"]) if total["tp"] + total["fn"] else 0
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if micro_precision + micro_recall
        else 0
    )
    return {
        "per_field": per_field,
        "macro_f1": round(sum(field_f1) / len(field_f1), 6) if field_f1 else 0,
        "micro_precision": round(micro_precision, 6),
        "micro_recall": round(micro_recall, 6),
        "micro_f1": round(micro_f1, 6),
        "hallucination_rate": round(invented / predicted_values, 6) if predicted_values else 0,
        "human_correction_case_rate": round(corrected_cases / len(cases), 6) if cases else 0,
    }


def git_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else None


def git_is_dirty() -> bool | None:
    result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=False
    )
    return bool(result.stdout.strip()) if result.returncode == 0 else None


def ffprobe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def run_asr(case: dict, settings: Settings, profile: str) -> tuple[str, dict]:
    from econstat.services.transcription import Transcriber

    audio_path = Path(case["audio_path"])
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio introuvable : {audio_path}")
    duration = ffprobe_duration(audio_path)
    started = time.perf_counter()
    segments = Transcriber(settings, profile=profile).transcribe(audio_path)
    elapsed = time.perf_counter() - started
    transcript = " ".join(segment.text for segment in segments)
    return transcript, {
        "audio_seconds": round(duration, 6),
        "transcription_seconds": round(elapsed, 6),
        "real_time_factor": round(elapsed / duration, 6) if duration else None,
    }


def subgroup_metrics(cases: list[dict], case_results: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for case, result in zip(cases, case_results, strict=True):
        for group in case.get("groups", ["non_classe"]):
            grouped[group].append(result)
    output = {}
    for group, results in sorted(grouped.items()):
        wers = [
            item["wer"]["wer"] for item in results if (item.get("wer") or {}).get("wer") is not None
        ]
        output[group] = {
            "cases": len(results),
            "wer_mean": round(sum(wers) / len(wers), 6) if wers else None,
            "extraction_seconds_mean": round(
                sum(item["extraction_seconds"] for item in results) / len(results), 6
            ),
        }
    return output


def slot_metrics(cases: list[dict], predictions: list[dict]) -> dict:
    """Métriques spécialisées ; null reste explicite lorsque le manifeste n'est pas annoté."""
    field_names = {
        "lastname": "exact_match_lastname",
        "firstname": "exact_match_firstname",
        "date_accident": "date_accuracy",
        "heure_accident": "time_accuracy",
        "accident_datetime": "datetime_accuracy",
        "telephone_assure": "phone_accuracy",
        "plaque": "plate_accuracy",
    }
    output = {}
    for field, metric_name in field_names.items():
        comparisons = []
        for case, prediction in zip(cases, predictions, strict=True):
            truth = case.get("expected_data", {})
            if field in truth:
                comparisons.append(
                    normalise_text(truth[field]) == normalise_text(prediction.get(field))
                )
        output[metric_name] = (
            round(sum(comparisons) / len(comparisons), 6) if comparisons else None
        )
    location_top1 = [case.get("location_top1_correct") for case in cases]
    location_top3 = [case.get("location_top3_correct") for case in cases]
    location_top1 = [value for value in location_top1 if value is not None]
    location_top3 = [value for value in location_top3 if value is not None]
    confirmations = [case.get("confirmed") for case in cases if "confirmed" in case]
    output.update(
        {
            "wer_proper_names": None,
            "location_top1_accuracy": (
                round(sum(location_top1) / len(location_top1), 6) if location_top1 else None
            ),
            "location_top3_accuracy": (
                round(sum(location_top3) / len(location_top3), 6) if location_top3 else None
            ),
            "confirmation_rate": (
                round(sum(bool(value) for value in confirmations) / len(confirmations), 6)
                if confirmations
                else None
            ),
            "status": "mesure_partielle_selon_annotations",
        }
    )
    return output


def benchmark(manifest_path: Path, profile: str, run_asr_enabled: bool) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = manifest.get("cases", [])
    if not cases:
        raise ValueError("Le manifeste ne contient aucun cas.")
    settings = Settings(ollama_enabled=False, enable_llm=False, processing_profile=profile)
    lexicon = LocalLexicon(settings.lexicon_path)
    predictions = []
    case_results = []
    diarization_results = []
    tracemalloc.start()
    run_started = time.perf_counter()
    for case in cases:
        operational = {}
        if run_asr_enabled:
            transcript, operational = run_asr(case, settings, profile)
        else:
            transcript = case.get("transcript", "")
        started = time.perf_counter()
        extraction = extract_rules(transcript, lexicon)
        extraction_seconds = time.perf_counter() - started
        prediction = extraction.data
        predictions.append(prediction)
        reference = case.get("reference_transcript")
        wer = word_error_rate(reference, transcript) if reference is not None else None
        case_results.append(
            {
                "id": case["id"],
                "groups": case.get("groups", []),
                "wer": wer,
                "extraction_seconds": round(extraction_seconds, 6),
                "predicted_fields": sorted(prediction),
                **operational,
            }
        )
        if "reference_turns" in case and "hypothesis_turns" in case:
            diarization_results.append(
                diarization_error_rate(case["reference_turns"], case["hypothesis_turns"])
            )
    total_seconds = time.perf_counter() - run_started
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    model_path = (
        Path(settings.whisper_fast_model)
        if profile == "fast"
        else Path(settings.whisper_quality_model)
    )
    wer_results = [item["wer"] for item in case_results if item["wer"] is not None]
    wer_errors = sum(item["errors"] for item in wer_results)
    wer_words = sum(item["reference_words"] for item in wer_results)
    audio_seconds = sum(item.get("audio_seconds", 0) for item in case_results)
    transcription_seconds = sum(item.get("transcription_seconds", 0) for item in case_results)
    diarization_reference = sum(item["reference_seconds"] for item in diarization_results)
    diarization_errors = sum(
        item["missed_seconds"] + item["false_alarm_seconds"] + item["confusion_seconds"]
        for item in diarization_results
    )
    lock_path = Path("requirements.lock")
    return {
        "experiment_id": str(uuid.uuid4()),
        "date": datetime.now(UTC).isoformat(),
        "git_commit": git_commit(),
        "git_dirty": git_is_dirty(),
        "python_version": platform.python_version(),
        "dependency_lock_hash": sha256_file(lock_path) if lock_path.is_file() else None,
        "model_name": str(model_path),
        "model_revision": (
            settings.whisper_revision if profile == "quality" else settings.whisper_distil_revision
        ),
        "model_file_hash": sha256_tree(model_path) if run_asr_enabled else None,
        "dataset_version": manifest.get("dataset_version", "non_versionne"),
        "dataset_hash": sha256_file(manifest_path),
        "random_seed": settings.llm_seed,
        "processing_profile": profile,
        "machine_info": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
        },
        "parameters": {
            "run_asr": run_asr_enabled,
            "llm_enabled": False,
            "allow_model_downloads": settings.allow_model_downloads,
        },
        "metrics": {
            "transcription": {
                "wer": round(wer_errors / wer_words, 6) if wer_words else None,
                "errors": wer_errors,
                "reference_words": wer_words,
                "status": "mesure" if wer_words else "non_mesurable_sans_reference",
            },
            "extraction": score_extraction(cases, predictions),
            "business_slots": slot_metrics(cases, predictions),
            "subgroups": subgroup_metrics(cases, case_results),
            "operational": {
                "cases": len(cases),
                "total_seconds": round(total_seconds, 6),
                "python_peak_memory_mb": round(peak_memory / 1024 / 1024, 3),
                "audio_seconds": round(audio_seconds, 6) if run_asr_enabled else None,
                "transcription_seconds": (
                    round(transcription_seconds, 6) if run_asr_enabled else None
                ),
                "real_time_factor": (
                    round(transcription_seconds / audio_seconds, 6)
                    if run_asr_enabled and audio_seconds
                    else None
                ),
            },
            "diarization": (
                {
                    "der": (
                        round(diarization_errors / diarization_reference, 6)
                        if diarization_reference
                        else None
                    ),
                    "cases": len(diarization_results),
                    "status": "mesure",
                }
                if diarization_results
                else {
                    "der": None,
                    "cases": 0,
                    "status": "non_mesurable_sans_annotations_de_tours",
                }
            ),
        },
        "cases": case_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/demo/benchmark_manifest.json"))
    parser.add_argument("--profile", choices=("fast", "quality"), default="fast")
    parser.add_argument(
        "--run-asr",
        action="store_true",
        help="Exécute le modèle local configuré ; aucun téléchargement implicite.",
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = benchmark(arguments.manifest, arguments.profile, arguments.run_asr)
    output = arguments.output or Path("experiments") / f"{result['experiment_id']}.local.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Benchmark enregistré : {output}")
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
