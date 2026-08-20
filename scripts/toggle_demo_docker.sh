#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

wait_before_close() {
    echo
    read -r -p "Appuyez sur Entree pour fermer cette fenetre..." _answer
}

trap wait_before_close EXIT

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker n'est pas installe."
    exit 1
fi

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
    echo "Le moteur Docker n'est pas actif."
    echo "Demarrez Docker Desktop, puis cliquez de nouveau sur le bouton."
    exit 1
fi

running_containers="$(docker compose ps --status running --quiet 2>/dev/null || true)"

if [[ -n "$running_containers" ]]; then
    echo "Arret d'E-Constat IA..."
    docker compose down
    echo "E-Constat IA est arrete. Les modeles sont conserves."
else
    echo "Demarrage d'E-Constat IA..."
    "$PROJECT_DIR/scripts/start_demo_docker.sh"
fi
