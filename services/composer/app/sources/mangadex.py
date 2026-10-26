from __future__ import annotations

import asyncio
from typing import Any

import httpx

API = "https://api.mangadex.org"
UA = "manhwa-ost/0.1 (local reader)"
LANG = "en"


class MangaDexError(RuntimeError):
    pass


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=API,
        headers={"User-Agent": UA},
        timeout=httpx.Timeout(30.0, connect=10.0),
        follow_redirects=True,
    )


def _title(attrs: dict) -> str:
    t = attrs.get("title") or {}
    return t.get("en") or next(iter(t.values()), "Untitled")


def _cover(rel: dict, manga_id: str) -> str | None:
    for r in rel:
        if r.get("type") == "cover_art":
            name = r["attributes"]["fileName"]
            return f"https://uploads.mangadex.org/covers/{manga_id}/{name}.512.jpg"
    return None


async def search(query: str, limit: int = 20) -> list[dict]:
    params: list[tuple[str, str]] = [
        ("limit", str(limit)),
        ("title", query),
        ("order[relevance]", "desc"),
        ("contentRating[]", "safe"),
        ("contentRating[]", "suggestive"),
        ("includes[]", "cover_art"),
    ]
    params.append(("availableTranslatedLanguage[]", LANG))
    async with _client() as c:
        r = await c.get("/manga", params=params)
        if r.status_code != 200:
            raise MangaDexError(f"search failed: {r.status_code} {r.text[:200]}")
        return [_row(m) for m in r.json()["data"]]


async def popular(limit: int = 20, original_language: str | None = "ko") -> list[dict]:
    params: list[tuple[str, str]] = [
        ("limit", str(limit)),
        ("order[followedCount]", "desc"),
        ("contentRating[]", "safe"),
        ("contentRating[]", "suggestive"),
        ("includes[]", "cover_art"),
        ("availableTranslatedLanguage[]", LANG),
    ]
    if original_language:
        params.append(("originalLanguage[]", original_language))
    async with _client() as c:
        r = await c.get("/manga", params=params)
        if r.status_code != 200:
            raise MangaDexError(f"popular failed: {r.status_code} {r.text[:200]}")
        return [_row(m) for m in r.json()["data"]]


def _row(m: dict) -> dict:
    a = m["attributes"]
    return {
        "id": m["id"],
        "title": _title(a),
        "description": (a.get("description") or {}).get("en", ""),
        "status": a.get("status"),
        "year": a.get("year"),
        "original_language": a.get("originalLanguage"),
        "tags": [t["attributes"]["name"].get("en") for t in a.get("tags", [])][:6],
        "cover": _cover(m.get("relationships", []), m["id"]),
    }


async def manga(manga_id: str) -> dict:
    async with _client() as c:
        r = await c.get(f"/manga/{manga_id}", params={"includes[]": "cover_art"})
        if r.status_code != 200:
            raise MangaDexError(f"manga failed: {r.status_code}")
        row = _row(r.json()["data"])
        row["cover"] = _cover(r.json()["data"].get("relationships", []), manga_id)
        return row


async def chapters(manga_id: str, limit: int = 200) -> list[dict]:
    params: list[tuple[str, str]] = [
        ("limit", str(limit)),
        ("translatedLanguage[]", LANG),
        ("order[chapter]", "desc"),
        ("includeExternalUrl", "0"),
        ("contentRating[]", "safe"),
        ("contentRating[]", "suggestive"),
    ]
    async with _client() as c:
        r = await c.get(f"/manga/{manga_id}/feed", params=params)
        if r.status_code != 200:
            raise MangaDexError(f"feed failed: {r.status_code}")
        out = []
        for c_ in r.json()["data"]:
            a = c_["attributes"]
            if a.get("externalUrl"):
                continue
            out.append(
                {
                    "id": c_["id"],
                    "number": a.get("chapter"),
                    "title": a.get("title"),
                    "pages": a.get("pages"),
                    "published_at": a.get("publishAt"),
                }
            )
        return out


async def page_urls(chapter_id: str) -> tuple[list[str], dict]:
    async with _client() as c:
        r = await c.get(f"/at-home/server/{chapter_id}")
        if r.status_code != 200:
            raise MangaDexError(f"at-home failed: {r.status_code}")
        d = r.json()
    base, h = d["baseUrl"], d["chapter"]["hash"]
    data = d["chapter"]["data"]
    return [f"{base}/data/{h}/{name}" for name in data], {"hash": h, "count": len(data)}


async def fetch_bytes(url: str) -> bytes:
    async with httpx.AsyncClient(headers={"User-Agent": UA}, timeout=60.0, follow_redirects=True) as c:
        r = await c.get(url)
        r.raise_for_status()
        return r.content


async def download_pages(urls: list[str], dest, limit: int | None = None, cache_dir=None) -> list:
    import hashlib

    dest.mkdir(parents=True, exist_ok=True)
    out = []
    sem = asyncio.Semaphore(4)

    async def one(i: int, url: str) -> None:
        async with sem:
            data = await fetch_bytes(url)
            p = dest / f"{i:03d}.jpg"
            p.write_bytes(data)
            if cache_dir is not None:
                key = hashlib.sha1(url.encode()).hexdigest()
                target = cache_dir / key[:2] / key
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    target.write_bytes(data)
            out.append(p)

    picks = list(enumerate(urls[:limit] if limit else urls, start=1))
    await asyncio.gather(*(one(i, u) for i, u in picks))
    return sorted(out)
