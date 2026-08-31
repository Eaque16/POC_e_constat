"""Mesure reproductible de la latence ASR interactive dans un même processus.

Le script sépare le chargement du modèle, le décodage PyAV, le VAD Silero,
l'inférence Faster-Whisper et le parser déterministe. Il ne télécharge jamais
de modèle et n'appelle ni Ollama, ni Pyannote, ni le réseau.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class RunTiming:
    decode: float
    vad: float
    asr: float
    parser: float
    persistence: float
    total: float
    audio_duration: float
    realtime_factor: float
    transcript: str


def percentile_95(values: list[float]) -> float:
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    position = 0.95 * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def summary(values: list[float]) -> str:
    return (
        f"moyenne={statistics.fmean(values):.3f} s  "
        f"médiane={statistics.median(values):.3f} s  "
        f"p95={percentile_95(values):.3f} s"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path, help="Audio local à retranscrire au moins cinq fois.")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--cpu-threads", type=int, default=0)
    parser.add_argument("--num-workers", type=int, default=1)
    parser.add_argument(
        "--json", action="store_true", help="Affiche aussi les mesures structurées."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.runs < 5:
        raise SystemExit("--runs doit être supérieur ou égal à 5.")
    audio_path = args.audio.resolve()
    if not audio_path.is_file():
        raise SystemExit(f"Audio introuvable : {audio_path}")

    import_started = perf_counter()
    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio
    from faster_whisper.vad import collect_chunks, get_speech_timestamps

    from econstat.config import get_settings
    from econstat.database import Base
    from econstat.models import Call, Claim, User
    from econstat.services.field_router import parse_expected_field
    from econstat.services.lexicon import LocalLexicon
    from econstat.services.transcription import local_model_missing_files

    import_seconds = perf_counter() - import_started
    settings = get_settings()
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(username="benchmark", hashed_password="synthetic")
        call = Call(owner=user, audio_path="benchmark://synthetic", segments_json=[])
        claim = Claim(call=call, data_json={})
        db.add(claim)
        db.commit()
        claim_id = claim.id
    model_path = Path(settings.whisper_fast_model).resolve()
    missing = local_model_missing_files(model_path)
    if missing:
        raise SystemExit(
            f"Modèle fast local incomplet ({model_path}) : {', '.join(missing)}. "
            "Aucun téléchargement automatique n'est autorisé."
        )

    print(f"IMPORTS         : {import_seconds:.3f} s")
    print("ASR model loading...")
    load_started = perf_counter()
    model = WhisperModel(
        str(model_path),
        device="cpu",
        compute_type="int8",
        cpu_threads=args.cpu_threads,
        num_workers=args.num_workers,
        local_files_only=True,
    )
    model_load_seconds = perf_counter() - load_started
    print(f"MODEL LOAD      : {model_load_seconds:.3f} s")
    print("ASR model ready")

    vocabulary = LocalLexicon(settings.lexicon_path).speech_vocabulary()
    hotwords = ", ".join(vocabulary)[:500]

    def timed_run() -> RunTiming:
        total_started = perf_counter()
        decode_started = perf_counter()
        audio = decode_audio(str(audio_path), sampling_rate=16000)
        decode_seconds = perf_counter() - decode_started
        audio_duration = len(audio) / 16000

        vad_started = perf_counter()
        speech = get_speech_timestamps(audio)
        speech_audio = collect_chunks(audio, speech) if speech else audio
        vad_seconds = perf_counter() - vad_started

        asr_started = perf_counter()
        raw_segments, _info = model.transcribe(
            speech_audio,
            language="fr",
            beam_size=1,
            vad_filter=False,
            condition_on_previous_text=True,
            initial_prompt="Déclaration automobile en Côte d’Ivoire.",
            hotwords=hotwords,
            word_timestamps=False,
        )
        transcript = " ".join(segment.text.strip() for segment in raw_segments).strip()
        asr_seconds = perf_counter() - asr_started

        parser_started = perf_counter()
        parsed = parse_expected_field(
            "circumstances", transcript or "parole non détectée", {}, asr_confidence=0.75
        )
        parser_seconds = perf_counter() - parser_started

        persistence_started = perf_counter()
        with Session(engine) as db:
            claim = db.get(Claim, claim_id)
            claim.model_trace_json = {"benchmark_field": parsed}
            db.commit()
        persistence_seconds = perf_counter() - persistence_started
        total_seconds = perf_counter() - total_started
        return RunTiming(
            decode=decode_seconds,
            vad=vad_seconds,
            asr=asr_seconds,
            parser=parser_seconds,
            persistence=persistence_seconds,
            total=total_seconds,
            audio_duration=audio_duration,
            realtime_factor=total_seconds / audio_duration if audio_duration else 0.0,
            transcript=transcript,
        )

    warmup_started = perf_counter()
    warmup = timed_run()
    warmup_seconds = perf_counter() - warmup_started
    print(f"WARMUP          : {warmup_seconds:.3f} s")
    print("ASR warm-up complete")

    runs: list[RunTiming] = []
    for index in range(1, args.runs + 1):
        timing = timed_run()
        runs.append(timing)
        print(f"\nRUN {index}")
        print(f"decode          : {timing.decode:.3f} s")
        print(f"vad             : {timing.vad:.3f} s")
        print(f"asr             : {timing.asr:.3f} s")
        print(f"parser          : {timing.parser:.3f} s")
        print(f"persistence     : {timing.persistence:.3f} s")
        print(f"total           : {timing.total:.3f} s")
        print(f"audio duration  : {timing.audio_duration:.3f} s")
        print(f"real-time factor: {timing.realtime_factor:.3f}")
        print(f"transcript      : {timing.transcript or '<vide>'}")

    print("\nWARM INFERENCE SUMMARY")
    for field in ("decode", "vad", "asr", "parser", "persistence", "total", "realtime_factor"):
        values = [float(getattr(item, field)) for item in runs]
        print(f"{field:16}: {summary(values)}")
    cold_start = import_seconds + model_load_seconds + warmup_seconds
    print(f"\nCOLD START TOTAL: {cold_start:.3f} s")
    print(
        "Note : le total cold start additionne imports, création du modèle et warm-up ; "
        "la persistance mesure un commit SQLAlchemy/SQLite en mémoire, sans transport HTTP."
    )
    if args.json:
        import json

        print(
            json.dumps(
                {
                    "environment": {
                        "model": str(model_path),
                        "device": "cpu",
                        "compute_type": "int8",
                        "cpu_threads": args.cpu_threads,
                        "num_workers": args.num_workers,
                    },
                    "imports_seconds": import_seconds,
                    "model_load_seconds": model_load_seconds,
                    "warmup_seconds": warmup_seconds,
                    "warmup": asdict(warmup),
                    "runs": [asdict(item) for item in runs],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
