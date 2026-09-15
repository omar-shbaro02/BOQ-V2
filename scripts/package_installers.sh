#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OUTPUT_DIR="$ROOT_DIR/dist/installers"
STAGING_DIR=$(mktemp -d)
trap 'rm -rf "$STAGING_DIR"' EXIT INT TERM

mkdir -p "$OUTPUT_DIR" "$STAGING_DIR/vai-local-evaluation"
tar \
  --exclude=.git \
  --exclude=.venv \
  --exclude=node_modules \
  --exclude=.next \
  --exclude=dist \
  --exclude=.data \
  --exclude=.pytest_cache \
  -C "$ROOT_DIR" -cf - . | tar -C "$STAGING_DIR/vai-local-evaluation" -xf -

chmod +x "$STAGING_DIR/vai-local-evaluation/install-linux.sh"
tar -C "$STAGING_DIR" -czf "$OUTPUT_DIR/vai-local-evaluation-linux.tar.gz" vai-local-evaluation
(
  cd "$STAGING_DIR"
  zip -qr "$OUTPUT_DIR/vai-local-evaluation-windows.zip" vai-local-evaluation
)

echo "Created:"
echo "  $OUTPUT_DIR/vai-local-evaluation-linux.tar.gz"
echo "  $OUTPUT_DIR/vai-local-evaluation-windows.zip"
