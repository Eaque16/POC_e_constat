#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OLLAMA_BIN="$PROJECT_DIR/.tools/ollama/bin/ollama"

if [[ ! -x "$OLLAMA_BIN" ]]; then
    echo "Ollama local est absent. Consultez le README pour l'installation."
    exit 1
fi

export OLLAMA_MODELS="$PROJECT_DIR/.tools/ollama-models"
export OLLAMA_HOST="127.0.0.1:11434"
export OLLAMA_VULKAN="false"
export OLLAMA_CONTEXT_LENGTH="2048"
export OLLAMA_KEEP_ALIVE="10m"

exec "$OLLAMA_BIN" serve
