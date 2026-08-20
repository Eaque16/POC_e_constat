import os
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from backend.app.api.transcription import (
    save_upload_temporarily,
    transcribe_uploaded_audio,
    validate_upload_filename,
)


class FakeUpload:
    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self._content = content
        self._consumed = False
        self.closed = False

    async def read(self, _size: int) -> bytes:
        if self._consumed:
            return b""
        self._consumed = True
        return self._content

    async def close(self) -> None:
        self.closed = True


class ValidateUploadFilenameTests(TestCase):
    def test_accepts_extension_case_insensitively(self) -> None:
        self.assertEqual(validate_upload_filename("constat.WAV"), ".wav")

    def test_rejects_unsupported_extension(self) -> None:
        with self.assertRaises(HTTPException) as context:
            validate_upload_filename("notes.txt")

        self.assertEqual(context.exception.status_code, 415)


class SaveUploadTests(IsolatedAsyncioTestCase):
    async def test_rejects_empty_file(self) -> None:
        upload = FakeUpload(filename="vide.wav", content=b"")

        with self.assertRaises(HTTPException) as context:
            await save_upload_temporarily(upload, ".wav")  # type: ignore[arg-type]

        self.assertEqual(context.exception.status_code, 400)

    async def test_rejects_file_over_configured_limit(self) -> None:
        upload = FakeUpload(filename="trop-grand.wav", content=b"1234")

        with patch.dict(os.environ, {"MAX_AUDIO_SIZE": "3"}):
            with self.assertRaises(HTTPException) as context:
                await save_upload_temporarily(upload, ".wav")  # type: ignore[arg-type]

        self.assertEqual(context.exception.status_code, 413)


class TranscriptionEndpointTests(IsolatedAsyncioTestCase):
    async def test_returns_structured_transcription_and_removes_temporary_file(
        self,
    ) -> None:
        upload = FakeUpload(filename="constat.wav", content=b"audio-fictif")
        observed_path: Path | None = None

        def fake_transcription(path: Path) -> dict[str, str | float]:
            nonlocal observed_path
            observed_path = path
            self.assertTrue(path.is_file())
            return {
                "text": "Accident a Cocody.",
                "language": "fr",
                "language_probability": 0.98,
                "duration": 3.2,
                "segments": [
                    {"start": 0.0, "end": 3.2, "text": "Accident a Cocody."}
                ],
            }

        async def fake_threadpool(function, *args):
            return function(*args)

        with (
            patch(
                "backend.app.api.transcription.transcribe_audio",
                side_effect=fake_transcription,
            ),
            patch(
                "backend.app.api.transcription.run_in_threadpool",
                new=AsyncMock(side_effect=fake_threadpool),
            ),
        ):
            response = await transcribe_uploaded_audio(upload)  # type: ignore[arg-type]

        self.assertEqual(response.text, "Accident a Cocody.")
        self.assertEqual(response.language, "fr")
        self.assertIsNotNone(observed_path)
        self.assertFalse(observed_path.is_file())
        self.assertTrue(upload.closed)
