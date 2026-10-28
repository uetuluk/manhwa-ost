#!/usr/bin/env bash
# Fetch the pinned audio.cpp source that tools/build-engine.sh builds.
#
#   tools/fetch-engine.sh          clone at $AUDIOCPP_PIN (shallow)
#   tools/fetch-engine.sh --check  report the checkout and its commit
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/env.sh"

if [[ "${1:-}" == "--check" ]]; then
    if [[ -d "$AUDIOCPP_SRC/src/models/yue2" ]]; then
        printf '%s\n' "$AUDIOCPP_SRC"
        git -C "$AUDIOCPP_SRC" log -1 --format='%H %s' 2>/dev/null || echo "(no git metadata)"
    else
        echo "MISSING $AUDIOCPP_SRC"
        exit 1
    fi
    exit 0
fi

if [[ -d "$AUDIOCPP_SRC/src/models/yue2" ]]; then
    echo "already present: $AUDIOCPP_SRC"
    exit 0
fi

mkdir -p "$(dirname "$AUDIOCPP_SRC")"
git init -q "$AUDIOCPP_SRC"
git -C "$AUDIOCPP_SRC" remote add origin https://github.com/0xShug0/audio.cpp.git
git -C "$AUDIOCPP_SRC" fetch -q --depth 1 origin "$AUDIOCPP_PIN"
git -C "$AUDIOCPP_SRC" checkout -q FETCH_HEAD

echo "fetched audio.cpp @ $AUDIOCPP_PIN -> $AUDIOCPP_SRC"
echo "next: tools/build-engine.sh"
