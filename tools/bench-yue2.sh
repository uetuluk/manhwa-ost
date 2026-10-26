#!/usr/bin/env bash
# Y1 smoke/benchmark: one YuE2 render on HIP with VRAM sampling.
#   tools/bench-yue2.sh <name> [extra audiocpp args...]
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/env.sh"

name="${1:-run}"; shift || true
out_dir="$MANHWA_OST_DATA/spike/$name"
mkdir -p "$out_dir"
vram="/sys/class/drm/card2/device/mem_info_vram_used"

: > "$out_dir/vram.log"
( while :; do cat "$vram" >> "$out_dir/vram.log" 2>/dev/null || true; sleep 2; done ) &
sampler=$!
trap 'kill $sampler 2>/dev/null || true' EXIT

start=$(date +%s.%N)
/usr/bin/time -f "MAXRSS=%MKB" "$AUDIOCPP_BUILD/bin/audiocpp_cli" \
    --task gen --family yue2 --model "$YUE2_MODEL_ROOT" \
    --backend hip --threads 8 \
    --seed 1234 \
    --out "$out_dir/$(date +%H%M%S).wav" \
    --log "$@" 2>&1 | tee "$out_dir/cli.log" | tail -40
end=$(date +%s.%N)
kill $sampler 2>/dev/null || true

peak=$(sort -n "$out_dir/vram.log" | tail -1)
echo "WALL=$(echo "$end - $start" | bc)s VRAM_PEAK=$((peak/1024/1024))MiB"
for f in "$out_dir"/*.wav; do
    [ -f "$f" ] && ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$f"
done
