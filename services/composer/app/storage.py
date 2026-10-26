from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from . import config


def series_key(source: str, manga_id: str) -> str:
    return hashlib.sha1(f"{source}:{manga_id}".encode()).hexdigest()[:12]


def series_dir(source: str, manga_id: str) -> Path:
    d = config.LIBRARY_DIR / series_key(source, manga_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def chapter_dir(source: str, manga_id: str, chapter_id: str) -> Path:
    d = series_dir(source, manga_id) / chapter_id
    for sub in ("pages", "cues"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    return d


def read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def load_series_meta(source: str, manga_id: str) -> dict | None:
    return read_json(series_dir(source, manga_id) / "series.json")


def save_series_meta(source: str, manga_id: str, meta: dict) -> None:
    write_json(series_dir(source, manga_id) / "series.json", meta)


def load_score(source: str, manga_id: str, chapter_id: str) -> dict | None:
    return read_json(chapter_dir(source, manga_id, chapter_id) / "score.json")


def save_score(source: str, manga_id: str, chapter_id: str, score: dict) -> None:
    write_json(chapter_dir(source, manga_id, chapter_id) / "score.json", score)


def media_url(path: Path) -> str:
    rel = path.resolve().relative_to(config.LIBRARY_DIR.resolve())
    return f"/media/{rel.as_posix()}"


def reset_pages(source: str, manga_id: str, chapter_id: str) -> Path:
    d = chapter_dir(source, manga_id, chapter_id) / "pages"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    return d
