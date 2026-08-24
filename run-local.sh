#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python_bin=".venv-wsl/bin/python"
if [[ ! -x "$python_bin" ]]; then
  echo "Environnement WSL absent. Exécutez d'abord : bash setup.sh" >&2
  exit 1
fi

export DATABASE_URL="sqlite:///./econstat-local.db"
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export ECONSTA_BASE_URL="http://127.0.0.1:8001"
export ECONSTAT_API_URL="http://127.0.0.1:8000/api"
export ECONSTAT_UI_HOST="0.0.0.0"
export ECONSTAT_UI_PORT="7860"
export GRADIO_ANALYTICS_ENABLED="False"
export RECORDINGS_DIR="data/recordings"
export APP_ENV="local-wsl"
export ENABLE_LLM="false"
export DISABLE_AUTH="true"

mkdir -p .runtime-wsl
"$python_bin" -m econstat.local_bootstrap

pids=()
cleanup() {
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"$python_bin" -m uvicorn econstat.mock_server:app --host 0.0.0.0 --port 8001 \
  >.runtime-wsl/mock.log 2>&1 &
pids+=("$!")
"$python_bin" -m uvicorn econstat.main:app --host 0.0.0.0 --port 8000 \
  >.runtime-wsl/api.log 2>&1 &
pids+=("$!")
"$python_bin" -m econstat.ui.app >.runtime-wsl/ui.log 2>&1 &
pids+=("$!")

"$python_bin" - <<'PY'
import time
import urllib.request

endpoints = (
    "http://127.0.0.1:8001/openapi.json",
    "http://127.0.0.1:8000/health",
    "http://127.0.0.1:7860/config",
)
for endpoint in endpoints:
    for attempt in range(90):
        try:
            with urllib.request.urlopen(endpoint, timeout=2) as response:
                if response.status < 500:
                    break
        except Exception:
            time.sleep(1)
    else:
        raise SystemExit(f"Service indisponible : {endpoint}")
PY

echo "E-Constat IA est lancé dans WSL."
echo "Interface : http://localhost:7860"
echo "API       : http://localhost:8000/docs"
echo "Journaux  : .runtime-wsl/"
echo "Arrêt      : Ctrl+C"

wait -n "${pids[@]}"
