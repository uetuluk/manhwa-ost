#!/usr/bin/env bash
# Run the composer API on http://127.0.0.1:8765
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$MANHWA_OST_REPO/services/composer"
exec "${MANHWA_OST_DATA}/venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8765 "$@"
