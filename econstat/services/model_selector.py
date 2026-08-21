import subprocess
from dataclasses import dataclass

from econstat.config import Settings


@dataclass(frozen=True)
class ModelSelection:
    model: str
    vram_gb: float | None
    device: str


def detect_vram_gb() -> float | None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        values = [float(line.strip()) / 1024 for line in result.stdout.splitlines() if line.strip()]
        return max(values) if values else None
    except (FileNotFoundError, subprocess.SubprocessError, ValueError):
        return None


def select_qwen_model(settings: Settings, vram_gb: float | None = None) -> ModelSelection:
    vram = detect_vram_gb() if vram_gb is None else vram_gb
    if vram is None:
        return ModelSelection(settings.ollama_model_cpu, None, "cpu")
    if vram >= settings.vram_threshold_27b_gb:
        model = settings.ollama_model_20gb
    elif vram >= settings.vram_threshold_14b_gb:
        model = settings.ollama_model_16gb
    elif vram >= settings.vram_threshold_8b_gb:
        model = settings.ollama_model_8gb
    else:
        model = settings.ollama_model_cpu
    return ModelSelection(model, round(vram, 2), "cuda")
