"""Run a real local transcription from the command line."""

import argparse
from pathlib import Path

from backend.app.services.transcription import transcribe_audio


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcrire un fichier audio local")
    parser.add_argument("audio_path", type=Path, help="Chemin du fichier audio")
    args = parser.parse_args()

    result = transcribe_audio(args.audio_path)

    print("\n--- TRANSCRIPTION ---")
    print(result["text"])
    print("\n--- INFORMATIONS ---")
    print("Langue :", result["language"])
    print("Probabilité langue :", result["language_probability"])
    print("Durée :", result["duration"])


if __name__ == "__main__":
    main()
