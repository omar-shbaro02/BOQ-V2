#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
COMPOSE_FILE="$ROOT_DIR/compose.installer.yml"

if command -v podman >/dev/null 2>&1 && podman info >/dev/null 2>&1; then
  COMPOSE="podman compose"
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  COMPOSE="docker compose"
else
  echo "Docker with Compose or Podman with Compose is required and must be running." >&2
  exit 1
fi

case "${1:-start}" in
  stop)
    $COMPOSE -f "$COMPOSE_FILE" down
    echo "VAI stopped. Local data was preserved."
    exit 0
    ;;
  reset)
    $COMPOSE -f "$COMPOSE_FILE" down --volumes
    echo "VAI stopped and local database/evidence volumes were removed."
    exit 0
    ;;
  start) ;;
  *) echo "Usage: ./install-linux.sh [start|stop|reset]" >&2; exit 2 ;;
esac

echo "Building and starting VAI. The first installation can take several minutes..."
$COMPOSE -f "$COMPOSE_FILE" up -d --build

ATTEMPT=0
until curl --fail --silent http://localhost:8000/health >/dev/null 2>&1; do
  ATTEMPT=$((ATTEMPT + 1))
  if [ "$ATTEMPT" -ge 60 ]; then
    echo "VAI started but did not become healthy. Inspect the container logs." >&2
    exit 1
  fi
  sleep 2
done

echo "VAI is ready at http://localhost:3000"
echo "This package is for local evaluation and usability testing, not production deployment."
if command -v xdg-open >/dev/null 2>&1 && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
  xdg-open http://localhost:3000 >/dev/null 2>&1 || true
fi
