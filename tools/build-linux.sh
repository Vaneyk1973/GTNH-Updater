#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
python3 -m PyInstaller --clean --noconfirm --onefile --console --name gtnh-updater --add-data "lib/cacert.pem:lib" gtnh_updater.py
