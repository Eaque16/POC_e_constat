#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

docker_is_ready() {
    timeout 3 docker info >/dev/null 2>&1
}

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker n'est pas installe. Installez ou demarrez Docker Desktop."
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose n'est pas disponible."
    exit 1
fi

if ! docker_is_ready; then
    current_context="$(docker context show 2>/dev/null || true)"
    for candidate in desktop-linux default; do
        if [[ "$candidate" == "$current_context" ]]; then
            continue
        fi
        if DOCKER_CONTEXT="$candidate" docker_is_ready; then
            export DOCKER_CONTEXT="$candidate"
            echo "Contexte Docker utilise : $candidate"
            break
        fi
    done
fi

if ! docker_is_ready; then
    echo "Le moteur Docker n'est pas actif. Demarrez Docker Desktop, puis relancez :"
    echo "  ./scripts/start_demo_docker.sh"
    exit 1
fi

echo "Construction et demarrage d'E-Constat IA..."
docker compose up --build --detach --remove-orphans

echo "Attente de l'interface..."
frontend_healthy=false
for _attempt in $(seq 1 30); do
    frontend_id="$(docker compose ps --quiet frontend 2>/dev/null || true)"
    if [[ -n "$frontend_id" ]] && \
        [[ "$(docker inspect --format '{{.State.Health.Status}}' "$frontend_id" 2>/dev/null || true)" == "healthy" ]]; then
        frontend_healthy=true
        break
    fi
    sleep 2
done

if [[ "$frontend_healthy" != "true" ]]; then
    echo "L'interface n'est pas devenue operationnelle. Derniers journaux :"
    docker compose logs --tail 80 backend frontend ollama
    exit 1
fi

echo
docker compose ps
echo
echo "E-Constat IA est pret :"
echo "  Interface : http://127.0.0.1:7860"
echo "  API       : http://127.0.0.1:8000"
echo "  Swagger   : http://127.0.0.1:8000/docs"
echo
echo "Journaux : docker compose logs -f"
echo "Arret     : ./scripts/stop_demo_docker.sh"
