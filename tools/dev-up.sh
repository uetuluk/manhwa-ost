#!/usr/bin/env bash
# Start composer + reader dev server if they are not already listening.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/env.sh"

logs="$MANHWA_OST_DATA/logs"
mkdir -p "$logs" "$MANHWA_OST_DATA/run"

if ! curl -sf -o /dev/null http://127.0.0.1:8765/api/health; then
    nohup "$MANHWA_OST_REPO/tools/run-composer.sh" > "$logs/composer.log" 2>&1 &
    echo $! > "$MANHWA_OST_DATA/run/composer.pid"
    echo "composer: started (pid $(cat "$MANHWA_OST_DATA/run/composer.pid"))"
else
    echo "composer: already up"
fi

if ! curl -sf -o /dev/null http://127.0.0.1:5173/; then
    nohup npm --prefix "$MANHWA_OST_REPO/apps/web-reader" run dev -- --host 127.0.0.1 > "$logs/vite.log" 2>&1 &
    echo $! > "$MANHWA_OST_DATA/run/vite.pid"
    echo "reader: started (pid $(cat "$MANHWA_OST_DATA/run/vite.pid"))"
else
    echo "reader: already up"
fi

for _ in $(seq 1 30); do
    if curl -sf -o /dev/null http://127.0.0.1:8765/api/health && curl -sf -o /dev/null http://127.0.0.1:5173/; then
        echo "ready: http://127.0.0.1:5173"
        exit 0
    fi
    sleep 1
done

echo "one of the services did not come up; see $logs" >&2
exit 1
