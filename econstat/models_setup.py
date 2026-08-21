import subprocess
from pathlib import Path

from huggingface_hub import snapshot_download

from econstat.config import get_settings
from econstat.services.model_selector import select_qwen_model


def main():
    settings = get_settings()
    source = Path("models/whisper-source")
    target = Path("models/whisper-ct2")
    snapshot_download(
        repo_id=settings.whisper_model, revision=settings.whisper_revision, local_dir=source
    )
    if not (target / "model.bin").exists():
        subprocess.run(
            [
                "ct2-transformers-converter",
                "--model",
                str(source),
                "--output_dir",
                str(target),
                "--copy_files",
                "tokenizer.json",
                "preprocessor_config.json",
                "--quantization",
                "float16",
            ],
            check=True,
        )
    if not settings.hf_token:
        raise RuntimeError("HF_TOKEN manque pour le modèle pyannote gated")
    if settings.diarization_revision == "main":
        raise RuntimeError(
            "Épinglez DIARIZATION_REVISION sur un SHA après obtention de l'accès gated"
        )
    snapshot_download(
        repo_id=settings.diarization_model,
        revision=settings.diarization_revision,
        token=settings.hf_token,
        local_dir="models/pyannote",
    )
    selected = select_qwen_model(settings)
    subprocess.run(["ollama", "pull", selected.model], check=True)
    print(
        "Modèles vérifiés : "
        f"Whisper {settings.whisper_revision}, "
        f"pyannote {settings.diarization_revision}, {selected.model}"
    )


if __name__ == "__main__":
    main()
