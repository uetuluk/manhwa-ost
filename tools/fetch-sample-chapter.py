#!/usr/bin/env python3
"""Fetch one sample chapter from MangaDex for reader/analysis spikes.

    tools/fetch-sample-chapter.py --out /srv/manhwa-ost/spike/sample

Writes pages as 001.png..., plus meta.json (series title, chapter, source ids).
MangaDex's public API needs no credentials; the User-Agent is required.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import urllib.parse
import urllib.request

API = "https://api.mangadex.org"
UA = "manhwa-ost-spike/0.1 (local research)"


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def get_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def search_manhwa(limit: int = 10) -> list[dict]:
    params = {
        "limit": limit,
        "originalLanguage[]": "ko",
        "order[followedCount]": "desc",
        "contentRating[]": ["safe", "suggestive"],
        "hasAvailableChapters": "true",
    }
    url = f"{API}/manga?" + urllib.parse.urlencode(params, doseq=True, safe="[]:")
    out = []
    for m in get(url)["data"]:
        a = m["attributes"]
        title = a["title"].get("en") or next(iter(a["title"].values()))
        out.append({"id": m["id"], "title": title, "status": a["status"]})
    return out


def english_chapters(manga_id: str) -> list[dict]:
    url = f"{API}/manga/{manga_id}/feed?" + urllib.parse.urlencode(
        {
            "limit": 100,
            "translatedLanguage[]": "en",
            "order[chapter]": "asc",
            "includeExternalUrl": "0",
            "contentRating[]": ["safe", "suggestive"],
        },
        doseq=True,
        safe="[]:",
    )
    rows = []
    for c in get(url)["data"]:
        a = c["attributes"]
        if a["externalUrl"]:
            continue
        rows.append({"id": c["id"], "chapter": a["chapter"], "title": a["title"], "pages": a["pages"]})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=pathlib.Path)
    ap.add_argument("--manga-id", default=None)
    ap.add_argument("--chapter", default=None)
    ap.add_argument("--max-pages", type=int, default=24)
    args = ap.parse_args()

    if args.manga_id:
        manga_id = args.manga_id
    else:
        picks = search_manhwa()
        if not picks:
            print("no manhwa found")
            return 1
        print("candidates:")
        for p in picks:
            print(f"  {p['id']}  {p['title']}  [{p['status']}]")
        manga_id = picks[0]["id"]

    manga = get(f"{API}/manga/{manga_id}?includes[]=cover_art")["data"]
    title = manga["attributes"]["title"].get("en") or next(iter(manga["attributes"]["title"].values()))

    chapters = [c for c in english_chapters(manga_id) if 6 <= (c["pages"] or 0) <= 40]
    if not chapters:
        print("no usable english chapters")
        return 1
    if args.chapter:
        chapters = [c for c in chapters if c["chapter"] == args.chapter] or chapters
    chapter = max(chapters, key=lambda c: c["pages"] or 0)

    pages_meta = get(f"{API}/at-home/server/{chapter['id']}")
    base = pages_meta["baseUrl"]
    h, ch = pages_meta["chapter"]["hash"], pages_meta["chapter"]["data"]
    if not ch:
        print("chapter has no image data (external)")
        return 1

    out = args.out / manga_id / (chapter["chapter"] or "0")
    out.mkdir(parents=True, exist_ok=True)
    for i, name in enumerate(ch[: args.max_pages], start=1):
        data = get_bytes(f"{base}/data/{h}/{name}")
        suffix = pathlib.Path(name).suffix or ".png"
        (out / f"{i:03d}{suffix}").write_bytes(data)

    (out / "meta.json").write_text(
        json.dumps(
            {
                "series_id": manga_id,
                "series_title": title,
                "chapter_id": chapter["id"],
                "chapter_number": chapter["chapter"],
                "chapter_title": chapter["title"],
                "page_count": len(ch[: args.max_pages]),
                "source": "mangadex",
            },
            indent=2,
        )
    )
    print(f"{title} ch.{chapter['chapter']} -> {out} ({len(ch[:args.max_pages])} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
