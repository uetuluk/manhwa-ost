#!/usr/bin/env python3
"""Audio fingerprint for cue QA: key, tempo, loudness, timbre, chroma.

    tools/analyze-audio.py FILE [FILE...] [--json]

Used to answer three questions about a generated cue:
  1. is it in the score book's key?          (key, chroma)
  2. is its tempo usable for crossfades?     (tempo, beat regularity)
  3. does it sit at the same loudness?       (LUFS)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import librosa
import numpy as np

PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def estimate_key(chroma_mean: np.ndarray) -> tuple[str, float]:
    best = ("?", 0.0)
    for i in range(12):
        for mode, tpl in (("maj", MAJOR), ("min", MINOR)):
            rotated = np.roll(tpl, i)
            score = float(np.corrcoef(chroma_mean, rotated)[0, 1])
            if score > best[1]:
                best = (f"{PITCH_CLASSES[i]} {mode}", score)
    return best


def fingerprint(path: Path) -> dict:
    y, sr = librosa.load(path, sr=22050, mono=True)
    duration = len(y) / sr

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)
    key, key_score = estimate_key(chroma_mean)

    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])
    ibi = np.diff(librosa.frames_to_time(beats, sr=sr))
    beat_regularity = float(1.0 - min(1.0, np.std(ibi) / np.mean(ibi))) if len(ibi) > 2 else 0.0

    rms = librosa.feature.rms(y=y)[0]
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    flatness = librosa.feature.spectral_flatness(y=y)[0]

    f0, voiced, _ = librosa.pyin(y, fmin=60, fmax=1200, sr=sr)
    f0v = f0[~np.isnan(f0)]
    f0_median = float(np.median(f0v)) if f0v.size else 0.0

    peak = float(np.max(np.abs(y)))
    return {
        "file": path.name,
        "duration_s": round(duration, 2),
        "key": key,
        "key_score": round(key_score, 3),
        "tempo_bpm": round(tempo, 1),
        "beat_regularity": round(beat_regularity, 3),
        "rms_db": round(float(20 * np.log10(np.mean(rms) + 1e-9)), 2),
        "peak_db": round(float(20 * np.log10(peak + 1e-9)), 2),
        "centroid_hz": round(float(np.mean(centroid)), 1),
        "flatness": round(float(np.mean(flatness)), 4),
        "f0_median_hz": round(f0_median, 1),
        "chroma": [round(float(c), 4) for c in chroma_mean],
    }


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--json"]
    as_json = "--json" in sys.argv
    out = [fingerprint(Path(a)) for a in args]
    if as_json:
        print(json.dumps(out, indent=2))
        return 0

    cols = ["duration_s", "key", "key_score", "tempo_bpm", "beat_regularity", "rms_db", "peak_db", "centroid_hz", "f0_median_hz"]
    print(f"{'file':<22}" + "".join(f"{c:>15}" for c in cols))
    for row in out:
        print(f"{row['file']:<22}" + "".join(f"{str(row[c]):>15}" for c in cols))

    if len(out) > 1:
        chroma = np.array([r["chroma"] for r in out])
        print("\nchroma similarity (cosine):")
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                a, b = chroma[i], chroma[j]
                sim = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
                print(f"  {out[i]['file']} vs {out[j]['file']}: {sim:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
