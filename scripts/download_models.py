"""Téléchargement explicite d’un modèle Faster-Whisper CTranslate2."""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Télécharge explicitement un dépôt CTranslate2 compatible Faster-Whisper."
    )
    parser.add_argument("--source", required=True, help="Dépôt Hugging Face, avec licence vérifiée")
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--confirm-download",
        action="store_true",
        help="Confirmation obligatoire du téléchargement réseau",
    )
    arguments = parser.parse_args()
    if not arguments.confirm_download:
        raise SystemExit(
            "Ajoutez --confirm-download après vérification de la source et de la licence."
        )
    if arguments.destination.exists() and any(arguments.destination.iterdir()):
        raise SystemExit(f"Destination non vide, refus d’écraser : {arguments.destination}")

    from huggingface_hub import snapshot_download

    arguments.destination.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=arguments.source,
        local_dir=arguments.destination,
        local_dir_use_symlinks=False,
    )
    print(f"Modèle téléchargé explicitement dans {arguments.destination}")


if __name__ == "__main__":
    main()
