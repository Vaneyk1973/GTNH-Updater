#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
if [[ -x "$SCRIPT_DIR/gtnh-updater" ]]; then
    exec "$SCRIPT_DIR/gtnh-updater" "$@"
fi
exec python3 "$SCRIPT_DIR/gtnh_updater.py" "$@"
