from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from backend.app.services.transcription import transcribe_audio, validate_audio_path


class ValidateAudioPathTests(TestCase):
    def test_rejects_missing_file(self) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "introuvable"):
            validate_audio_path("audio-absent.wav")

    def test_rejects_unsupported_extension(self) -> None:
        file_path = Path(self._testMethodName + ".txt")
        file_path.touch()
        self.addCleanup(file_path.unlink)

        with self.assertRaisesRegex(ValueError, "non pris en charge"):
            validate_audio_path(file_path)


class TranscribeAudioTests(TestCase):
    def test_returns_joined_non_empty_segments(self) -> None:
        audio_path = Path(self._testMethodName + ".wav")
        audio_path.touch()
        self.addCleanup(audio_path.unlink)
        model = Mock()
        model.transcribe.return_value = (
            iter(
                [
                    SimpleNamespace(text=" Bonjour ", start=0.0, end=0.8),
                    SimpleNamespace(text=" ", start=0.8, end=1.0),
                    SimpleNamespace(text="Cocody.", start=1.0, end=2.0),
                ]
            ),
            SimpleNamespace(
                language="fr", language_probability=0.99, duration=2.5
            ),
        )

        with patch(
            "backend.app.services.transcription.get_whisper_model",
            return_value=model,
        ):
            result = transcribe_audio(audio_path)

        self.assertEqual(result["text"], "Bonjour Cocody.")
        self.assertEqual(result["language"], "fr")
        self.assertEqual(result["language_probability"], 0.99)
        self.assertEqual(result["duration"], 2.5)
        self.assertEqual(len(result["segments"]), 2)
        self.assertEqual(result["segments"][1]["start"], 1.0)
        call_arguments = model.transcribe.call_args
        self.assertEqual(call_arguments.args, (str(audio_path.resolve()),))
        self.assertEqual(call_arguments.kwargs["language"], "fr")
        self.assertEqual(call_arguments.kwargs["beam_size"], 3)
        self.assertEqual(call_arguments.kwargs["max_new_tokens"], 128)
        self.assertTrue(call_arguments.kwargs["vad_filter"])
        self.assertFalse(call_arguments.kwargs["condition_on_previous_text"])
        self.assertIn("Cocody", call_arguments.kwargs["hotwords"])
        self.assertIsNone(call_arguments.kwargs["initial_prompt"])

    def test_configures_max_new_tokens_from_environment(self) -> None:
        audio_path = Path(self._testMethodName + ".wav")
        audio_path.touch()
        self.addCleanup(audio_path.unlink)
        model = Mock()
        model.transcribe.return_value = (
            iter([]),
            SimpleNamespace(language="fr", language_probability=1.0, duration=0.0),
        )

        with (
            patch(
                "backend.app.services.transcription.get_whisper_model",
                return_value=model,
            ),
            patch.dict("os.environ", {"WHISPER_MAX_NEW_TOKENS": "96"}),
        ):
            transcribe_audio(audio_path)

        self.assertEqual(model.transcribe.call_args.kwargs["max_new_tokens"], 96)

    def test_initial_prompt_disables_hotwords_to_stay_below_model_limit(self) -> None:
        audio_path = Path(self._testMethodName + ".wav")
        audio_path.touch()
        self.addCleanup(audio_path.unlink)
        model = Mock()
        model.transcribe.return_value = (
            iter([]),
            SimpleNamespace(language="fr", language_probability=1.0, duration=0.0),
        )

        with (
            patch(
                "backend.app.services.transcription.get_whisper_model",
                return_value=model,
            ),
            patch.dict(
                "os.environ",
                {
                    "WHISPER_INITIAL_PROMPT": "Contexte personnalise",
                    "WHISPER_HOTWORDS": "Cocody",
                },
            ),
        ):
            transcribe_audio(audio_path)

        arguments = model.transcribe.call_args.kwargs
        self.assertEqual(arguments["initial_prompt"], "Contexte personnalise")
        self.assertIsNone(arguments["hotwords"])
