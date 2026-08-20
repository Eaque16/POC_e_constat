"""HTTP endpoint for local audio transcription."""

import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from backend.app.schemas.transcription import TranscriptionResponse
from backend.app.services.transcription import (
    ALLOWED_AUDIO_EXTENSIONS,
    transcribe_audio,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audio", tags=["audio"])

DEFAULT_MAX_AUDIO_SIZE = 25 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 1024 * 1024


def get_max_audio_size() -> int:
    """Read the upload limit in bytes and reject invalid configuration."""

    value = int(os.getenv("MAX_AUDIO_SIZE", str(DEFAULT_MAX_AUDIO_SIZE)))
    if value <= 0:
        raise ValueError("MAX_AUDIO_SIZE doit etre un entier strictement positif")
    return value


def validate_upload_filename(filename: str | None) -> str:
    """Validate the client filename and return its normalized extension."""

    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le fichier audio doit avoir un nom.",
        )

    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_AUDIO_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_AUDIO_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Format audio non pris en charge. Formats autorises : {allowed}",
        )
    return extension


async def save_upload_temporarily(upload: UploadFile, extension: str) -> Path:
    """Stream a size-limited upload to a temporary local file."""

    max_size = get_max_audio_size()
    total_size = 0
    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temporary:
            temporary_path = Path(temporary.name)
            while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                total_size += len(chunk)
                if total_size > max_size:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Le fichier audio depasse la limite de {max_size} octets.",
                    )
                temporary.write(chunk)

        if total_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le fichier audio est vide.",
            )
        return temporary_path
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise


@router.post(
    "/transcribe",
    response_model=TranscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Transcrire un fichier audio localement",
)
async def transcribe_uploaded_audio(
    audio: UploadFile = File(description="Audio WAV, MP3, M4A, OGG ou WebM"),
) -> TranscriptionResponse:
    """Validate, temporarily store, and transcribe an uploaded audio file."""

    extension = validate_upload_filename(audio.filename)
    temporary_path: Path | None = None
    try:
        temporary_path = await save_upload_temporarily(audio, extension)
        logger.info("Audio accepte pour transcription")
        result = await run_in_threadpool(transcribe_audio, temporary_path)
        logger.info("Transcription terminee; duree_audio=%.2f", result["duration"])
        return TranscriptionResponse(**result)
    except HTTPException:
        raise
    except (FileNotFoundError, ValueError) as error:
        logger.warning("Audio refuse: %s", error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except Exception as error:
        logger.exception("Echec de la transcription locale")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="La transcription locale a echoue.",
        ) from error
    finally:
        await audio.close()
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
