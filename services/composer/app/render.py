from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

from . import config

MOOD_STYLE = {
    "calm": "gentle, unhurried, soft dynamics",
    "tense": "restless, sustained dissonance, ticking pulse",
    "battle": "driving percussion, low brass, aggressive accents",
    "grief": "slow, minor, solo lines, room to breathe",
    "mystery": "sparse, unresolved harmony, glassy textures",
    "triumph": "rising brass, broad melody statement, full ensemble",
    "dread": "low drone, unresolved pedal, distant percussion",
    "wonder": "bright bells, celesta, wide airy pads",
    "comic": "pizzicato, light woodwind, playful rhythm",
    "romance": "warm strings, lyrical lead, soft pulse",
}


def cue_id_for(section: dict) -> str:
    energy = float(section.get("energy", 0.5))
    bucket = "low" if energy < 0.35 else "mid" if energy < 0.7 else "high"
    return f"{section['motif']}-{bucket}"


def cue_spec(section: dict, style_note: str | None = None) -> dict:
    moods = [MOOD_STYLE.get(m, m) for m in section.get("mood", [])]
    arrangement = section.get("arrangement") or ""
    style = ", ".join(x for x in [arrangement, *moods, style_note, "instrumental", "no vocals"] if x)
    return {
        "cue_id": cue_id_for(section),
        "style": style[:400],
        "motif": section["motif"],
        "energy": section.get("energy", 0.5),
        "tension": section.get("tension", 0.5),
    }


def seed_for(series_title: str, motif: str) -> int:
    # Stable per series+motif so every chapter's version of a motif shares a
    # character instead of a fresh roll of the dice.
    h = 0
    for ch in f"{series_title}|{motif}":
        h = (h * 131 + ord(ch)) & 0x7FFFFFFF
    return h


def render_cue(spec: dict, out_wav: Path, *, series_title: str, abc: Path, log_path: Path | None = None) -> Path:
    n_frames = int(config.CUE_SECONDS * config.FRAMES_PER_SECOND)
    cmd = [
        str(config.AUDIOCPP_CLI),
        "--task", "gen",
        "--family", "yue2",
        "--model", str(config.YUE2_MODEL_ROOT),
        "--backend", "hip",
        "--threads", "8",
        "--lyrics", "",
        "--session-option", f"yue2.ar_lora={config.YUE2_AR_LORA}",
        "--session-option", "yue2.ar_lora_scale=1.0",
        "--request-option", f"style={spec['style']}",
        "--request-option", "cot=full",
        "--request-option", f"abc_file={abc}",
        "--request-option", f"semantic_max_tokens={n_frames}",
        "--request-option", "num_inference_steps=8",
        "--seed", str(seed_for(series_title, spec["motif"])),
        "--out", str(out_wav),
    ]
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    log = open(log_path, "w") if log_path else subprocess.DEVNULL
    try:
        proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=1800, text=True)
    finally:
        if log_path:
            log.close()
    if proc.returncode != 0 or not out_wav.exists():
        raise RuntimeError(f"yue2 render failed for {spec['cue_id']} (exit {proc.returncode})")
    return out_wav


def analyze(wav: Path) -> dict:
    tool = config.REPO_DIR / "tools" / "analyze-audio.py"
    py = config.DATA_DIR / "venv" / "bin" / "python"
    proc = subprocess.run(
        [str(py), str(tool), str(wav), "--json"], capture_output=True, text=True, timeout=600
    )
    if proc.returncode != 0:
        raise RuntimeError(f"analysis failed: {proc.stderr[-400:]}")
    return json.loads(proc.stdout)[0]


def to_opus(wav: Path, opus: Path) -> Path:
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
        "-c:a", "libopus", "-b:a", "112k", "-vbr", "on", str(opus),
    ]
    subprocess.run(cmd, check=True, timeout=600)
    return opus


def loop_points(duration: float, energy: float) -> dict:
    """A usable loop window; beat alignment is added later with onset data."""
    fade_in = min(6.0, duration * 0.15)
    loop_start = round(fade_in + (0.5 if energy > 0.6 else 0.0), 2)
    loop_end = round(max(loop_start + 8.0, duration - 2.0), 2)
    return {"start": loop_start, "end": loop_end}


def build_cue(spec: dict, cue_dir: Path, *, series_title: str, abc: Path) -> dict:
    cue_dir.mkdir(parents=True, exist_ok=True)
    wav = cue_dir / f"{spec['cue_id']}.wav"
    opus = cue_dir / f"{spec['cue_id']}.opus"
    if not wav.exists():
        render_cue(spec, wav, series_title=series_title, abc=abc, log_path=cue_dir / f"{spec['cue_id']}.log")
    if not opus.exists():
        to_opus(wav, opus)
    fp = analyze(wav)
    duration = float(fp["duration_s"])
    return {
        "src": opus.name,
        "duration_s": duration,
        "key": fp["key"],
        "tempo_bpm": fp["tempo_bpm"],
        "loudness_db": fp["rms_db"],
        "loop": loop_points(duration, float(spec.get("energy", 0.5))),
        "style": spec["style"],
        "motif": spec["motif"],
    }
