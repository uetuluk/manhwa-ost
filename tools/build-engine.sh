#!/usr/bin/env bash
# Build (or check) the YuE2 audio.cpp engine for HIP gfx1201.
#
#   tools/build-engine.sh              configure + build audiocpp_cli and audiocpp_server
#   tools/build-engine.sh --check      report the built binary and its backends
#   tools/build-engine.sh --clean      remove the build dir before configuring
#
# Host compiler is gcc (libgomp for OpenMP); HIP compilation is delegated to
# clang++ 21 through CMAKE_HIP_ARCHITECTURES. Setting CMAKE_C(XX)_COMPILER to the
# HIP clang breaks FindOpenMP on this box.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/env.sh"

mode=build
for arg in "$@"; do
    case "$arg" in
        --check) mode=check ;;
        --clean) mode=clean ;;
        *) echo "unknown argument: $arg" >&2; exit 2 ;;
    esac
done

bin_cli="$AUDIOCPP_BUILD/bin/audiocpp_cli"
bin_srv="$AUDIOCPP_BUILD/bin/audiocpp_server"

if [[ "$mode" == check ]]; then
    for b in "$bin_cli" "$bin_srv"; do
        if [[ -x "$b" ]]; then
            printf '%s\n' "$b"
            "$b" --version 2>/dev/null | head -2 || true
        else
            printf 'MISSING %s\n' "$b"
        fi
    done
    exit 0
fi

if [[ "$mode" == clean ]]; then
    rm -rf "$AUDIOCPP_BUILD"
fi

if [[ ! -d "$AUDIOCPP_SRC/src/models/yue2" ]]; then
    echo "engine source not found at $AUDIOCPP_SRC" >&2
    exit 1
fi

cmake -S "$AUDIOCPP_SRC" -B "$AUDIOCPP_BUILD" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DAUDIOCPP_MODEL_SET=custom \
    -DAUDIOCPP_MODELS="$AUDIOCPP_MODELS" \
    -DENGINE_ENABLE_HIP=ON \
    -DENGINE_ENABLE_CUDA=OFF \
    -DENGINE_ENABLE_CUDA_GRAPHS=ON \
    -DENGINE_ENABLE_LLAMAFILE=ON \
    -DENGINE_ENABLE_NATIVE_CPU=ON \
    -DENGINE_ENABLE_VULKAN=OFF \
    -DENGINE_ENABLE_OPENMP=ON \
    -DCMAKE_HIP_ARCHITECTURES=gfx1201 \
    -DAUDIOCPP_BUILD_NATIVE_MODEL_MANAGER=OFF \
    -DAUDIOCPP_BUILD_SERVER_FRONTENDS=OFF \
    -DENGINE_BUILD_EXAMPLES=OFF \
    -DENGINE_BUILD_TESTS=OFF \
    -DENGINE_BUILD_WARMBENCH=OFF 2>&1 | tail -15

cmake --build "$AUDIOCPP_BUILD" --parallel "$(nproc)" \
    --target audiocpp_cli audiocpp_server

echo
echo "built:"
for b in "$bin_cli" "$bin_srv"; do
    [[ -x "$b" ]] && { printf '  %s\n' "$b"; "$b" --version 2>/dev/null | head -2 || true; }
done
