#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

docker_is_ready() {
    timeout 3 docker info >/dev/null 2>&1
}

if ! docker_is_ready; then
    current_context="$(docker context show 2>/dev/null || true)"
    for candidate in desktop-linux default; do
        if [[ "$candidate" == "$current_context" ]]; then
            continue
        fi
        if DOCKER_CONTEXT="$candidate" docker_is_ready; then
            export DOCKER_CONTEXT="$candidate"
            break
        fi
    done
fi

if ! docker_is_ready; then
    echo "Aucun moteur Docker actif n'a ete trouve."
    exit 1
fi

docker compose down
echo "E-Constat IA est arrete. Les modeles telecharges sont conserves."
