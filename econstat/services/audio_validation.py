"""Validation et stockage défensifs des fichiers audio entrants."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from econstat.config import Settings

MIME_TYPES_BY_SUFFIX = {
    ".wav": frozenset({"audio/wav", "audio/wave", "audio/x-wav"}),
    ".mp3": frozenset({"audio/mpeg", "audio/mp3"}),
    ".m4a": frozenset({"audio/mp4", "audio/x-m4a", "video/mp4"}),
    ".ogg": frozenset({"audio/ogg", "application/ogg"}),
    ".flac": frozenset({"audio/flac", "audio/x-flac"}),
}
GENERIC_BINARY_MIME = "application/octet-stream"
FORMAT_NAMES_BY_SUFFIX = {
    ".wav": frozenset({"wav"}),
    ".mp3": frozenset({"mp3"}),
    ".m4a": frozenset({"mov", "mp4", "m4a", "3gp", "3g2", "mj2"}),
    ".ogg": frozenset({"ogg"}),
    ".flac": frozenset({"flac"}),
}
CHUNK_SIZE = 1024 * 1024


class AudioValidationError(Exception):
    def __init__(self, status_code: int, code: str, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class AudioProbe:
    duration_seconds: float
    format_name: str
    codecs: tuple[str, ...]


@dataclass(frozen=True)
class StoredAudio:
    storage_id: str
    path: Path
    sha256: str
    size_bytes: int
    duration_seconds: float
    mime_type: str
    format_name: str


def validate_declared_type(upload: UploadFile, suffix: str) -> str:
    mime_type = (upload.content_type or GENERIC_BINARY_MIME).split(";", 1)[0].strip().lower()
    allowed = MIME_TYPES_BY_SUFFIX.get(suffix, frozenset()) | {GENERIC_BINARY_MIME}
    if mime_type not in allowed:
        raise AudioValidationError(
            415,
            "audio_mime_not_allowed",
            f"Type MIME incompatible avec l'extension {suffix}.",
        )
    return mime_type


def probe_audio(path: Path, suffix: str, settings: Settings) -> AudioProbe:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise AudioValidationError(
            503,
            "ffprobe_unavailable",
            "ffprobe est requis pour valider les fichiers audio. Installez FFmpeg.",
        )
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=format_name,duration:stream=codec_type,codec_name",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        raise AudioValidationError(
            422, "audio_probe_timeout", "L'inspection du fichier audio a expiré."
        ) from exc
    if result.returncode != 0:
        raise AudioValidationError(
            415,
            "audio_container_invalid",
            "Le fichier n'est pas un conteneur audio lisible par ffprobe.",
        )
    try:
        payload = json.loads(result.stdout)
        format_data = payload.get("format", {})
        format_name = str(format_data.get("format_name", "")).lower()
        duration = float(format_data.get("duration", 0))
        audio_streams = [
            stream for stream in payload.get("streams", []) if stream.get("codec_type") == "audio"
        ]
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AudioValidationError(
            415, "audio_metadata_invalid", "Les métadonnées audio sont invalides."
        ) from exc

    detected_formats = frozenset(part.strip() for part in format_name.split(",") if part.strip())
    if not detected_formats.intersection(FORMAT_NAMES_BY_SUFFIX[suffix]):
        raise AudioValidationError(
            415,
            "audio_extension_mismatch",
            "Le conteneur audio réel ne correspond pas à l'extension déclarée.",
        )
    if not audio_streams:
        raise AudioValidationError(415, "audio_stream_missing", "Aucune piste audio détectée.")
    if not math.isfinite(duration) or duration <= 0:
        raise AudioValidationError(422, "audio_duration_invalid", "Durée audio invalide.")
    if duration > settings.max_audio_duration_seconds:
        raise AudioValidationError(
            413,
            "audio_duration_exceeded",
            f"La durée dépasse la limite de {settings.max_audio_duration_seconds} secondes.",
        )
    codecs = tuple(str(stream.get("codec_name", "unknown")) for stream in audio_streams)
    return AudioProbe(round(duration, 3), format_name, codecs)


def validate_and_store_audio(upload: UploadFile, settings: Settings) -> StoredAudio:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in settings.allowed_audio_suffixes or suffix not in MIME_TYPES_BY_SUFFIX:
        raise AudioValidationError(
            415,
            "audio_extension_not_allowed",
            "Extension audio non autorisée.",
        )
    mime_type = validate_declared_type(upload, suffix)
    if not shutil.which("ffprobe"):
        raise AudioValidationError(
            503,
            "ffprobe_unavailable",
            "ffprobe est requis pour valider les fichiers audio. Installez FFmpeg.",
        )

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    storage_id = str(uuid.uuid4())
    final_path = settings.upload_dir / f"{storage_id}{suffix}"
    partial_path = settings.upload_dir / f".{storage_id}.part"
    max_bytes = settings.max_audio_mb * 1024 * 1024
    size_bytes = 0
    digest = hashlib.sha256()

    try:
        with partial_path.open("xb") as destination:
            while chunk := upload.file.read(CHUNK_SIZE):
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    raise AudioValidationError(
                        413,
                        "audio_size_exceeded",
                        f"Le fichier dépasse la limite de {settings.max_audio_mb} Mo.",
                    )
                digest.update(chunk)
                destination.write(chunk)
        if size_bytes == 0:
            raise AudioValidationError(422, "audio_empty", "Le fichier audio est vide.")
        probe = probe_audio(partial_path, suffix, settings)
        partial_path.replace(final_path)
    except Exception:
        partial_path.unlink(missing_ok=True)
        final_path.unlink(missing_ok=True)
        raise

    return StoredAudio(
        storage_id=storage_id,
        path=final_path,
        sha256=digest.hexdigest(),
        size_bytes=size_bytes,
        duration_seconds=probe.duration_seconds,
        mime_type=mime_type,
        format_name=probe.format_name,
    )
