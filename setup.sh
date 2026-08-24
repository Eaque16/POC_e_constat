#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Un environnement distinct évite de mélanger les binaires Windows et Linux
# lorsque le dépôt est ouvert depuis /mnt/c sous WSL.
python_command="${PYTHON_COMMAND:-python3.11}"
if ! command -v "$python_command" >/dev/null 2>&1; then
  python_command="python3"
fi
if ! command -v "$python_command" >/dev/null 2>&1; then
  echo "Python 3.11 est requis. Installez python3.11, python3.11-venv et ffmpeg." >&2
  exit 1
fi

"$python_command" -m venv .venv-wsl
source .venv-wsl/bin/activate
python -m pip install --upgrade pip==24.2
python -m pip install -r requirements.lock
python -m pip install -e '.[ai]'
cp -n .env.example .env || true

export DATABASE_URL="sqlite:///./econstat-local.db"
export DISABLE_AUTH="true"
export ENABLE_LLM="false"
alembic upgrade head
python -m econstat.seed

echo "Installation WSL terminée. Lancez : bash run-local.sh"
