from __future__ import annotations

import asyncio
import time

import httpx

API = "https://api.mangadex.org"
UA = "manhwa-ost/0.1 (local reader)"
LANG = "en"

# MangaDex keeps licensed series in the catalogue after the chapters are
# removed, so a manga list is not proof that anything is readable. Every
# browse result is probed once with a 1-item chapter feed and cached.
_PROBE_TTL = 600
_PROBE_CACHE: dict[str, tuple[float, list[dict]]] = {}


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


def _cover(rel: list[dict], manga_id: str) -> str | None:
    for r in rel:
        if r.get("type") == "cover_art":
            name = r["attributes"]["fileName"]
            return f"https://uploads.mangadex.org/covers/{manga_id}/{name}.512.jpg"
    return None


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


async def _probe(client: httpx.AsyncClient, manga: list[dict], limit: int, sort_by_date: bool) -> list[dict]:
    sem = asyncio.Semaphore(3)
    alive: list[dict] = []

    async def one(m: dict) -> None:
        async with sem:
            await asyncio.sleep(0.15)  # stay inside the 5 req/s budget
            r = await client.get(
                f"/manga/{m['id']}/feed",
                params=[
                    ("limit", "1"),
                    ("translatedLanguage[]", LANG),
                    ("order[chapter]", "desc"),
                    ("includeExternalUrl", "0"),
                    ("contentRating[]", "safe"),
                    ("contentRating[]", "suggestive"),
                ],
            )
            if r.status_code != 200:
                return
            data = r.json().get("data", [])
            if not data:
                return
            ch = data[0]
            row = _row(m)
            row["latest_chapter"] = {
                "chapter_id": ch["id"],
                "number": ch["attributes"].get("chapter"),
                "title": ch["attributes"].get("title"),
                "pages": ch["attributes"].get("pages"),
                "published_at": ch["attributes"].get("publishAt"),
            }
            alive.append(row)

    await asyncio.gather(*(one(m) for m in manga))
    if sort_by_date:
        alive.sort(key=lambda x: x["latest_chapter"].get("published_at") or "", reverse=True)
    return alive[:limit]


async def latest(limit: int = 24, original_language: str | None = "ko") -> list[dict]:
    """Manhwa with readable English chapters, newest chapter first."""
    key = f"latest:{original_language}:{limit}"
    hit = _PROBE_CACHE.get(key)
    if hit and time.time() - hit[0] < _PROBE_TTL:
        return hit[1]

    params: list[tuple[str, str]] = [
        ("limit", "60"),
        ("order[latestUploadedChapter]", "desc"),
        ("contentRating[]", "safe"),
        ("contentRating[]", "suggestive"),
        ("hasAvailableChapters", "true"),
        ("includes[]", "cover_art"),
    ]
    if original_language:
        params.append(("originalLanguage[]", original_language))
    async with _client() as c:
        r = await c.get("/manga", params=params)
        if r.status_code != 200:
            raise MangaDexError(f"manga list failed: {r.status_code}")
        rows = await _probe(c, r.json()["data"], limit, sort_by_date=True)
    _PROBE_CACHE[key] = (time.time(), rows)
    return rows


async def popular(limit: int = 24, original_language: str | None = "ko") -> list[dict]:
    """Most-followed manhwa that still have readable chapters."""
    key = f"popular:{original_language}:{limit}"
    hit = _PROBE_CACHE.get(key)
    if hit and time.time() - hit[0] < _PROBE_TTL:
        return hit[1]

    params: list[tuple[str, str]] = [
        ("limit", "40"),
        ("order[followedCount]", "desc"),
        ("contentRating[]", "safe"),
        ("contentRating[]", "suggestive"),
        ("hasAvailableChapters", "true"),
        ("includes[]", "cover_art"),
    ]
    if original_language:
        params.append(("originalLanguage[]", original_language))
    async with _client() as c:
        r = await c.get("/manga", params=params)
        if r.status_code != 200:
            raise MangaDexError(f"popular failed: {r.status_code}")
        rows = await _probe(c, r.json()["data"], limit, sort_by_date=False)
    _PROBE_CACHE[key] = (time.time(), rows)
    return rows


async def search(query: str, limit: int = 20) -> list[dict]:
    params: list[tuple[str, str]] = [
        ("limit", str(limit)),
        ("title", query),
        ("order[relevance]", "desc"),
        ("contentRating[]", "safe"),
        ("contentRating[]", "suggestive"),
        ("includes[]", "cover_art"),
        ("availableTranslatedLanguage[]", LANG),
    ]
    async with _client() as c:
        r = await c.get("/manga", params=params)
        if r.status_code != 200:
            raise MangaDexError(f"search failed: {r.status_code} {r.text[:200]}")
        return [_row(m) for m in r.json()["data"]]


async def manga(manga_id: str) -> dict:
    async with _client() as c:
        r = await c.get(f"/manga/{manga_id}", params={"includes[]": "cover_art"})
        if r.status_code != 200:
            raise MangaDexError(f"manga failed: {r.status_code}")
        data = r.json()["data"]
        row = _row(data)
        row["cover"] = _cover(data.get("relationships", []), manga_id)
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
