# manhwa-ost

A manhwa reader whose soundtrack is composed for the page you are on.

The reader splits a chapter into *sections* (narrative beats), and each section
plays a cue from the series' own score: same leitmotifs, key and palette across
every chapter, different arrangement per section. Music is generated locally
with YuE2 on the R9700, the reading is analysed and scored by DeepSeek V4.1
Flash over the opencode-go subscription.

## Status

Phase 0 — feasibility spikes. Nothing here is a working reader yet.

| Spike | State |
| --- | --- |
| Y1 Yue2 HIP build on gfx1201 | **pass** — RTF 0.50, 6.7 GiB VRAM |
| Y2 ABC-conditioned motif consistency | **pass** — 3 styles, one key, chroma 0.96–0.98 |
| Y3 instrumental route (no vocals) | **pass (pending listen)** — LoRA, 46 s cue in 31 s |
| Y4 semantic-prefix cue continuity | **pass** — 50/50 frames identical |
| B1 storyboard → cue-sheet JSON | **pass** — 3/3 valid, 52–92 s |
| R1 source fetch → browser reader | **pass** — MangaDex → reader → composed chapter |

Measurements: [`docs/spikes-2026-10-26.md`](docs/spikes-2026-10-26.md).

## Shape

```
apps/web-reader/     browser reader (spike): sources, continuous scroll, cue engine
apps/reader/         Mihon fork (later, needs Android tooling)
services/composer/   analysis, score book, render queue, asset server
contracts/           JSON Schema, generated types
docs/                decisions, contracts, runbooks
tools/               bootstrap, engine build, benchmarks
```

Heavy artefacts (engine sources, builds, audio library) live on `/srv/manhwa-ost`,
not in the repo. See `tools/env.sh`.

## Run it

```bash
tools/run-composer.sh                 # API on 127.0.0.1:8765
npm --prefix apps/web-reader run dev  # reader on 127.0.0.1:5173
```

Open <http://127.0.0.1:5173>, pick MangaDex, open a series, open a chapter, press
**Compose OST** (≈90 s for a 20-page chapter: ~60 s reading the pages, ~30 s
composing five cues). Then press **Enable OST** and scroll; cues change at the
AI's section boundaries.

Deep links: `#/m/<mangaId>` for a series, `#/c/<mangaId>/<chapterId>` for a
chapter.

## Engine

YuE2 through [audio.cpp](https://github.com/0xShug0/audio.cpp), pinned at
`624cf918e51263d39c2a0d28a6c5e3d55990b79f`, built for HIP gfx1201 in its own
build directory. The drama3 build in `create-image-video-music` is not touched.

```bash
tools/build-engine.sh          # configure + build audiocpp_cli / audiocpp_server
tools/build-engine.sh --check  # report existing binary + backend
```

## Why the music stays consistent

1. The series score book is written as **ABC notation** — motifs are real
   melodies, not prompt adjectives.
2. Every cue is rendered with `cot=melody|full` + `abc_file` + a fixed seed, so
   the melody is the same by construction and only the arrangement changes.
3. Section transitions reuse `semantic_prefix_file` from the previous cue.
4. Post-processing locks key/BPM to the score book and normalises loudness.
