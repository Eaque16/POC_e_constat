#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip==24.2
python -m pip install -r requirements.lock
cp -n .env.example .env || true
if [[ "${INSTALL_AI:-0}" == "1" ]]; then python -m pip install '.[ai]'; python -m econstat.models_setup; fi
docker compose up -d postgres mock-econsta
alembic upgrade head
python -m econstat.seed
pytest
echo "Installation validée. API: uvicorn econstat.main:app --reload"
