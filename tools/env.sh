#!/usr/bin/env bash
# Shared paths. Source this from other tools; do not execute.

export MANHWA_OST_REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export MANHWA_OST_DATA="${MANHWA_OST_DATA:-/srv/manhwa-ost}"

# Engine
export AUDIOCPP_SRC="${AUDIOCPP_SRC:-$MANHWA_OST_DATA/engine/audio.cpp}"
export AUDIOCPP_BUILD="${AUDIOCPP_BUILD:-$MANHWA_OST_DATA/build/yue2}"
export AUDIOCPP_PIN="624cf918e51263d39c2a0d28a6c5e3d55990b79f"
export AUDIOCPP_MODELS="${AUDIOCPP_MODELS:-yue2;demucs}"

# Models
export YUE2_MODEL_ROOT="${YUE2_MODEL_ROOT:-/srv/models/yue2}"

# Outputs
export OST_LIBRARY="${OST_LIBRARY:-$MANHWA_OST_DATA/library}"
export OST_LOGS="${OST_LOGS:-$MANHWA_OST_DATA/logs}"
