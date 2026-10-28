from __future__ import annotations

import asyncio
import subprocess
import time
from pathlib import Path

from . import brain, config, jobs, render, storage
from .sources import mangadex

MAX_BRAIN_PAGES = 14
STORYBOARD_WIDTH = 760


def _downscale(pages: list[Path], dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for p in pages:
        target = dest / f"{p.stem}.jpg"
        if not target.exists():
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(p), "-vf", f"scale={STORYBOARD_WIDTH}:-1", str(target)],
                check=True,
                timeout=120,
            )
        out.append(target)
    return out


def _pick_storyboard(pages: list[Path], limit: int = MAX_BRAIN_PAGES) -> list[tuple[int, Path]]:
    """Evenly spaced sample of pages, with their real 1-based page numbers."""
    if len(pages) <= limit:
        return list(enumerate(pages, start=1))
    step = len(pages) / limit
    return [
        (min(len(pages), int(i * step) + 1), pages[min(len(pages) - 1, int(i * step))])
        for i in range(limit)
    ]


@jobs.runner("compose")
def compose(job: jobs.Job) -> dict:
    ref = job.ref
    source = ref.get("source", "mangadex")
    manga_id = ref["manga_id"]
    chapter_id = ref["chapter_id"]
    series_title = ref.get("series_title") or "Untitled"
    chapter_number = str(ref.get("chapter_number") or "?")
    chapter_title = ref.get("chapter_title")

    chapter = storage.chapter_dir(source, manga_id, chapter_id)
    t0 = time.time()

    jobs.update(job.id, progress=0.02, step="fetching page list")
    urls, meta = asyncio.run(mangadex.page_urls(chapter_id))

    jobs.update(job.id, progress=0.06, step=f"downloading {len(urls)} pages")
    pages_dir = storage.reset_pages(source, manga_id, chapter_id)
    pages = asyncio.run(mangadex.download_pages(urls, pages_dir, cache_dir=config.CACHE_DIR / "img"))
    page_count = len(pages)

    existing = storage.load_score(source, manga_id, chapter_id)
    if existing and not ref.get("force"):
        jobs.update(job.id, progress=0.95, step="using cached score")
        return existing

    jobs.update(job.id, progress=0.15, step="reading the chapter")
    board = _pick_storyboard(pages)
    images = _downscale([p for _, p in board], chapter / "storyboard")
    score = brain.score_chapter(
        images,
        series_title=series_title,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        page_count=page_count,
        page_numbers=[n for n, _ in board],
    )
    storage.write_json(chapter / "analysis.json", score)
    storage.save_score(source, manga_id, chapter_id, score)

    specs: dict[str, dict] = {}
    for section in score["sections"]:
        cid = render.cue_id_for(section)
        if cid not in specs:
            specs[cid] = render.cue_spec(section)

    abc = config.DEFAULT_ABC
    cue_dir = chapter / "cues"
    cues: dict[str, dict] = {}
    for i, (cid, spec) in enumerate(specs.items(), start=1):
        jobs.update(job.id, progress=0.15 + 0.75 * (i - 1) / max(1, len(specs)), step=f"composing cue {i}/{len(specs)} ({cid})")
        built = render.build_cue(spec, cue_dir, series_title=series_title, abc=abc)
        built["src"] = storage.media_url(cue_dir / built["src"])
        cues[cid] = built

    timeline = {
        "schema_version": 1,
        "series": {"title": series_title, "manga_id": manga_id, "source": source},
        "chapter": score["chapter"],
        "sections": [
            {**section, "cue_id": render.cue_id_for(section)} for section in score["sections"]
        ],
        "cues": cues,
        "music": {
            "abc": abc.name,
            "cue_seconds": config.CUE_SECONDS,
            "motifs": sorted({c["motif"] for c in cues.values()}),
        },
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "wall_seconds": round(time.time() - t0, 1),
    }
    storage.write_json(chapter / "timeline.json", timeline)
    jobs.update(job.id, progress=1.0, step="done")
    return timeline


@jobs.runner("analyze")
def analyze_only(job: jobs.Job) -> dict:
    ref = job.ref
    source = ref.get("source", "mangadex")
    manga_id, chapter_id = ref["manga_id"], ref["chapter_id"]
    chapter = storage.chapter_dir(source, manga_id, chapter_id)

    urls, _ = asyncio.run(mangadex.page_urls(chapter_id))
    pages_dir = storage.reset_pages(source, manga_id, chapter_id)
    pages = asyncio.run(mangadex.download_pages(urls, pages_dir, cache_dir=config.CACHE_DIR / "img"))
    board = _pick_storyboard(pages)
    images = _downscale([p for _, p in board], chapter / "storyboard")
    jobs.update(job.id, progress=0.3, step="reading the chapter")
    score = brain.score_chapter(
        images,
        series_title=ref.get("series_title") or "Untitled",
        chapter_number=str(ref.get("chapter_number") or "?"),
        chapter_title=ref.get("chapter_title"),
        page_count=len(pages),
        page_numbers=[n for n, _ in board],
    )
    storage.write_json(chapter / "analysis.json", score)
    storage.save_score(source, manga_id, chapter_id, score)
    return score
