from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, jobs, pipeline, storage
from .sources import mangadex

app = FastAPI(title="manhwa-ost composer", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_PAGES_CACHE: dict[str, tuple[float, dict]] = {}
PAGES_TTL = 60 * 30


class ComposeRequest(BaseModel):
    source: str = "mangadex"
    manga_id: str
    chapter_id: str
    series_title: str | None = None
    chapter_number: str | None = None
    chapter_title: str | None = None
    force: bool = False
    analyze_only: bool = False


@app.get("/api/health")
def health() -> dict:
    ok_cli = config.AUDIOCPP_CLI.exists()
    return {
        "ok": True,
        "engine": str(config.AUDIOCPP_CLI),
        "engine_present": ok_cli,
        "brain_model": config.BRAIN_MODEL,
        "library": str(config.LIBRARY_DIR),
    }


@app.get("/api/sources")
def sources() -> list[dict]:
    return [
        {
            "id": "mangadex",
            "name": "MangaDex",
            "languages": ["en"],
            "kinds": ["popular", "search"],
        }
    ]


@app.get("/api/mangadex/popular")
async def popular(limit: int = 18, original_language: str | None = "ko") -> list[dict]:
    return await mangadex.popular(limit=limit, original_language=original_language)


@app.get("/api/mangadex/latest")
async def latest(limit: int = 24) -> list[dict]:
    return await mangadex.latest(limit=limit)


@app.get("/api/mangadex/search")
async def search(q: str = Query(..., min_length=1), limit: int = 18) -> list[dict]:
    return await mangadex.search(q, limit=limit)


@app.get("/api/mangadex/manga/{manga_id}")
async def manga(manga_id: str) -> dict:
    meta = await mangadex.manga(manga_id)
    cached = storage.load_series_meta("mangadex", manga_id) or {}
    cached.update({k: v for k, v in meta.items() if v is not None})
    storage.save_series_meta("mangadex", manga_id, cached)
    return cached


@app.get("/api/mangadex/manga/{manga_id}/chapters")
async def chapters(manga_id: str) -> list[dict]:
    rows = await mangadex.chapters(manga_id)
    return rows


@app.get("/api/pages/{manga_id}/{chapter_id}")
async def local_pages(manga_id: str, chapter_id: str) -> dict:
    """Pages for reading: downloaded once, then served from disk.

    MangaDex at-home URLs are short-lived and node-specific, so reading must not
    depend on them — only composing does.
    """
    pages_dir = storage.chapter_dir("mangadex", manga_id, chapter_id) / "pages"
    files = sorted(pages_dir.glob("*.jpg"))
    if not files:
        urls, _ = await mangadex.page_urls(chapter_id)
        await mangadex.download_pages(urls, pages_dir, cache_dir=config.CACHE_DIR / "img")
        files = sorted(pages_dir.glob("*.jpg"))
    if not files:
        raise HTTPException(status_code=404, detail="chapter has no pages")
    return {
        "page_count": len(files),
        "pages": [f"/api/page/mangadex/{manga_id}/{chapter_id}/{i + 1}" for i in range(len(files))],
    }


@app.get("/api/page/{source}/{manga_id}/{chapter_id}/{index}")
def page_file(source: str, manga_id: str, chapter_id: str, index: int) -> FileResponse:
    path = storage.chapter_dir(source, manga_id, chapter_id) / "pages" / f"{index:03d}.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="page not found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/mangadex/chapter/{chapter_id}/pages")
async def chapter_pages(chapter_id: str, refresh: bool = False) -> dict:
    now = time.time()
    hit = _PAGES_CACHE.get(chapter_id)
    if hit and not refresh and now - hit[0] < PAGES_TTL:
        return hit[1]
    urls, meta = await mangadex.page_urls(chapter_id)
    data = {
        "chapter_id": chapter_id,
        "page_count": len(urls),
        "pages": [f"/api/image?u={_quote(u)}&n={i + 1:03d}" for i, u in enumerate(urls)],
    }
    if urls:
        cache_file = config.CACHE_DIR / "pages" / f"{chapter_id}.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({"urls": urls}))
    _PAGES_CACHE[chapter_id] = (now, data)
    return data


def _quote(url: str) -> str:
    from urllib.parse import quote

    return quote(url, safe="")


@app.get("/api/image")
async def image(u: str, n: str = "0") -> Response:
    # Local copy first: composing a chapter downloads every page.
    key = hashlib.sha1(u.encode()).hexdigest()
    cache_file = config.CACHE_DIR / "img" / key[:2] / key
    if cache_file.exists():
        return Response(content=cache_file.read_bytes(), media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
    try:
        data = await mangadex.fetch_bytes(u)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"image fetch failed: {exc}") from exc
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(data)
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})


@app.post("/api/compose")
def compose(req: ComposeRequest) -> dict:
    running = jobs.find_for(req.chapter_id)
    if running:
        return running.as_dict()
    kind = "analyze" if req.analyze_only else "compose"
    job = jobs.submit(kind, req.model_dump())
    return job.as_dict()


@app.get("/api/jobs/{job_id}")
def job(job_id: str) -> dict:
    j = jobs.get(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="job not found")
    return j.as_dict()


@app.get("/api/score/{source}/{manga_id}/{chapter_id}")
def score(source: str, manga_id: str, chapter_id: str) -> dict:
    chapter = storage.chapter_dir(source, manga_id, chapter_id)
    timeline = storage.read_json(chapter / "timeline.json")
    if timeline:
        return timeline
    analysis = storage.read_json(chapter / "analysis.json")
    if analysis:
        return {"schema_version": 1, "analysis_only": True, "sections": analysis["sections"], "cues": {}}
    raise HTTPException(status_code=404, detail="not composed yet")


@app.get("/api/library")
def library() -> list[dict]:
    out = []
    for d in sorted(config.LIBRARY_DIR.glob("*")):
        meta = storage.read_json(d / "series.json")
        if not meta:
            continue
        chapters = []
        for ch in sorted(d.iterdir()):
            if not ch.is_dir():
                continue
            tl = storage.read_json(ch / "timeline.json")
            an = storage.read_json(ch / "analysis.json")
            if not (tl or an):
                continue
            meta_ch = (tl or an).get("chapter", {})
            chapters.append(
                {
                    "chapter_id": ch.name,
                    "number": meta_ch.get("number"),
                    "title": meta_ch.get("title"),
                    "page_count": meta_ch.get("page_count"),
                    "composed": bool(tl),
                    "sections": len((tl or an)["sections"]),
                }
            )
        if chapters:
            out.append({"series": meta, "chapters": chapters})
    return out


config.LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=config.LIBRARY_DIR), name="media")
