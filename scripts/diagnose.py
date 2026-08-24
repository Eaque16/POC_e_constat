"""Diagnostic local Windows sans afficher de secret ni modifier la machine."""

from __future__ import annotations

import ctypes
import importlib.util
import json
import os
import platform
import sqlite3
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from econstat.config import Settings  # noqa: E402
from econstat.services.transcription import local_model_missing_files  # noqa: E402


def command_output(
    command: list[str], timeout: int = 8, first_line: bool = True
) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return False, "absent"
    output = (result.stdout or result.stderr).strip()
    if first_line and output:
        output = output.splitlines()[0]
    return result.returncode == 0, output or "sans réponse"


def windows_hardware() -> dict[str, object]:
    script = (
        "$cpu=(Get-ItemProperty -LiteralPath "
        "'HKLM:\\HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0' "
        "-ErrorAction SilentlyContinue).ProcessorNameString;"
        "$gpu=(Get-PnpDevice -Class Display -ErrorAction SilentlyContinue | "
        "Select-Object -ExpandProperty FriendlyName);"
        "if(-not $gpu){$gpu=(Get-ItemProperty -Path "
        "'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Video\\*\\0000' "
        "-ErrorAction SilentlyContinue | Where-Object {"
        "$_.PSObject.Properties.Name -contains 'DriverDesc'} | "
        "Select-Object -ExpandProperty DriverDesc)};"
        "[pscustomobject]@{cpu=$cpu;gpu=($gpu -join ', ')}|"
        "ConvertTo-Json -Compress"
    )
    ok, output = command_output(["powershell", "-NoProfile", "-Command", script])
    fallback = {"cpu": "indisponible", "gpu": "indisponible"}
    if not ok:
        return fallback
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return fallback


def ram_gb() -> float | str:
    if os.name != "nt":
        return "indisponible"

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("memory_load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong),
            ("available_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.length = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return "indisponible"
    return round(status.total_physical / (1024**3), 1)


def database_status(settings: Settings) -> tuple[bool, str]:
    if not settings.database_url.startswith("sqlite:///"):
        return False, "diagnostic automatique limité à SQLite"
    path = Path(settings.database_url.removeprefix("sqlite:///"))
    try:
        with sqlite3.connect(path) as connection:
            connection.execute("SELECT 1").fetchone()
        return True, str(path.resolve())
    except sqlite3.Error as exc:
        return False, f"erreur SQLite: {exc}"


def main() -> int:
    settings = Settings()
    hardware = windows_hardware()
    ffmpeg_ok, ffmpeg = command_output(["ffmpeg", "-version"])
    ffprobe_ok, ffprobe = command_output(["ffprobe", "-version"])
    ollama_ok, ollama = command_output(["ollama", "--version"])
    model_ok, models = command_output(["ollama", "list"], first_line=False)
    configured_ollama = settings.ollama_model.lower() in models.lower() if model_ok else False
    nvidia_ok, nvidia = command_output(
        ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"]
    )
    torch_found = importlib.util.find_spec("torch") is not None
    cuda_available = False
    if torch_found:
        try:
            import torch

            cuda_available = torch.cuda.is_available()
        except (ImportError, OSError):
            torch_found = False

    paths = {
        "uploads": settings.upload_dir,
        "recordings": settings.recordings_dir,
        "generated": settings.generated_dir,
        "models": settings.model_dir,
    }
    folders = {
        name: {
            "path": str(path),
            "accessible": path.exists() and os.access(path, os.R_OK | os.W_OK),
        }
        for name, path in paths.items()
    }
    database_ok, database = database_status(settings)
    whisper_fast_missing = local_model_missing_files(Path(settings.whisper_fast_model))
    whisper_quality_missing = local_model_missing_files(Path(settings.whisper_quality_model))
    whisper_fast = not whisper_fast_missing
    whisper_quality = not whisper_quality_missing
    pyannote_local = (settings.model_dir / "pyannote" / "config.yaml").exists()
    hf_token_present = bool(settings.hf_token)
    python_ok = sys.version_info[:2] == (3, 11)
    in_project_venv = Path(sys.prefix).resolve() == (PROJECT_ROOT / ".venv").resolve()
    core_ready = all([python_ok, in_project_venv, ffmpeg_ok, ffprobe_ok, database_ok]) and all(
        item["accessible"] for item in folders.values()
    )
    ai_ready = all(
        [
            torch_found,
            whisper_fast or whisper_quality,
            ollama_ok,
            configured_ollama,
            hf_token_present,
            pyannote_local,
        ]
    )
    overall = (
        "AI READY"
        if core_ready and ai_ready
        else "AI PARTIAL"
        if core_ready
        else "CORE NOT READY"
    )

    print("E-CONSTAT IA — DIAGNOSTIC WINDOWS")
    print(f"Python              : {platform.python_version()} ({platform.architecture()[0]})")
    print(f"Environnement .venv : {'OK' if in_project_venv else 'NON'}")
    print(f"Windows             : {platform.platform()}")
    print(f"CPU                 : {hardware.get('cpu')}")
    print(f"RAM (Go)            : {ram_gb()}")
    print(f"GPU                 : {hardware.get('gpu')}")
    print(f"NVIDIA              : {nvidia if nvidia_ok else 'absent'}")
    print(f"CUDA PyTorch        : {cuda_available}")
    print(f"FFmpeg              : {ffmpeg if ffmpeg_ok else 'absent'}")
    print(f"ffprobe             : {ffprobe if ffprobe_ok else 'absent'}")
    print(f"Ollama              : {ollama if ollama_ok else 'absent'}")
    print(f"Modèle Ollama       : {'présent' if configured_ollama else 'absent'}")
    print(f"HF_TOKEN            : {'présent' if hf_token_present else 'absent'}")
    fast_state = "prêt" if whisper_fast else f"incomplet ({', '.join(whisper_fast_missing)})"
    quality_state = (
        "prêt" if whisper_quality else f"incomplet ({', '.join(whisper_quality_missing)})"
    )
    print(f"Whisper fast        : {fast_state}")
    print(f"Whisper quality     : {quality_state}")
    print(f"pyannote local      : {'présent' if pyannote_local else 'absent'}")
    print(f"Base                : {'OK' if database_ok else 'ERREUR'} — {database}")
    for name, status in folders.items():
        state = "OK" if status["accessible"] else "ERREUR"
        print(f"Dossier {name:<11}: {state} — {status['path']}")
    print(overall)
    return 0 if core_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
