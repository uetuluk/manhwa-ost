# Pipeline

What happens between "open a chapter" and "music starts playing".

```
MangaDex ──► pages/            (downloaded once, served from disk)
              │
              ▼
        storyboard/*.jpg       (≤14 evenly spaced pages, 760 px)
              │
              ▼  opencode run --standalone --file …×14
        deepseek-v4.1-flash    → analysis.json  (3–8 sections)
              │
              ▼  one cue per distinct (motif, energy)
        Yue2 on HIP            → cues/<cue>-<hash>.wav
              │                    abc_file=ashen-crown.abc
              │                    cot=full + instrumental AR LoRA
              ▼
        ffmpeg → opus, librosa fingerprint (key/bpm/loop)
              │
              ▼
        timeline.json          → /api/score/… → reader
```

Storage is `/srv/manhwa-ost/library/<series_hash>/<chapter_id>/`:

```
pages/001.jpg …          original pages
storyboard/001.jpg …     the downscaled sample the brain actually saw
analysis.json            raw section sheet
cues/<cue>-<hash>.opus   one file per arrangement (hash = arrangement)
cues/<cue>-<hash>.wav    render master, kept for re-encoding
timeline.json            what the browser plays
```

## Why cues are cached by arrangement hash

A cue id is `(motif, energy bucket)` — `main-low`, `battle-high`. Two sections
that share a cue id share music *conceptually*, but the brain may brief them
differently (different instruments). The file name therefore includes a hash of
the arrangement string, so a changed brief re-renders instead of silently
reusing the old audio.

## Reader sync

The reader computes `(pageIndex, fraction)` from a probe line at 42% of the
viewport, then maps it to a section. On a section change it crossfades to that
section's cue; the fade length comes from the section's `transition_in`
(`cut` 0.7 s, `crossfade` 2.4 s, `swell` 4.5 s). New cues start at their loop
point (`intro_end`, currently 6 s) when the section is one page or the reader is
already past half of the page, so a fast scroll never replays a 6 s intro.

Cue looping uses the window in `timeline.json` (`loop.start`–`loop.end`), so a
50 s cue can cover a section however long the reader lingers.

## Known limits

- **Tempo detection is ambiguous** (83 vs 172 bpm for the same cue). Beat-aligned
  loops and tempo-locked transitions need onset data, not just a BPM estimate.
- **Arrangement reuse is per chapter.** Cross-chapter consistency of a motif is
  proven (same ABC → same key), but the series score book is not yet persisted:
  each chapter's analysis picks its own arrangements and seeds. A series-level
  score book is the next structural step.
- **MangaDex coverage** for licensed manhwa is thin (some series expose only a
  handful of chapters). Other sources need separate clients.
- **One job at a time.** The worker queue is single-threaded because Yue2 owns
  the GPU; a chapter takes 90–240 s depending on cue count and model latency.
- **`analysis.json` is not human-editable yet.** Re-rolling means `force=true`.
