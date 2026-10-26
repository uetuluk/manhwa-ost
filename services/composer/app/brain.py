from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path

from . import config

PROMPT = """You are scoring a manhwa chapter for a reader that plays a continuous soundtrack.

You are given pages 1..{page_count} of chapter {chapter_number}{chapter_title} of "{series_title}" as images, in order.

Split the chapter into 3 to 8 narrative SECTIONS. A section is a beat of the scene: it starts when the dramatic situation changes (new location, new intent, escalation, reveal, aftermath). Do not split more often than the art actually changes; do not merge an entire chapter into one beat.

Return ONLY a JSON object, no prose, no markdown fences, matching exactly this shape:

{{
  "schema_version": 1,
  "chapter": {{ "number": "{chapter_number}", "title": {chapter_title_json}, "page_count": {page_count} }},
  "sections": [
    {{
      "index": 1,
      "start_page": 1,
      "end_page": 3,
      "label": "short beat name, max 60 chars",
      "summary": "1-2 sentences of what happens",
      "mood": ["tense"],
      "energy": 0.35,
      "tension": 0.8,
      "motif": "main",
      "arrangement": "instrumentation tags, max 200 chars",
      "transition_in": "cut"
    }}
  ]
}}

Rules:
- Sections must be contiguous and cover pages 1..{page_count} with no gaps or overlaps.
- "mood" values are limited to: calm, tense, battle, grief, mystery, triumph, dread, wonder, comic, romance. Pick 1-3.
- "motif" is one of: {motifs}. Reuse the same motif id for moments that share a dramatic identity, even across sections.
- "energy" is how kinetic the pages are (fights and chases high, dialogue and aftermath low).
- "tension" is unresolved danger/anticipation, which can be high with low energy.
- "arrangement" is a music brief, not a story summary: name instruments, density, and register (e.g. "low strings ostinato, taiko accents, sparse high piano").
- "transition_in" is "cut" when the beat starts hard, "crossfade" when it bleeds in, "swell" when it builds from near silence.
"""

REPAIR = """Your previous answer was not valid JSON for the required schema.

Validation error: {error}

Return ONLY the corrected JSON object. No prose, no markdown fences. It must match this shape:

{schema}
"""


class BrainError(RuntimeError):
    pass


def _event_text(events_path: Path) -> str:
    text = []
    for line in events_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "text":
            text.append(ev["part"].get("text", ""))
    return "".join(text)


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.endswith("```"):
            t = t[:-3]
        t = t.removeprefix("json").strip()
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        t = t[start : end + 1]
    return t.strip()


def _run(images: list[Path], prompt: str, timeout: int) -> str:
    workdir = config.RUN_DIR / f"brain-{uuid.uuid4().hex[:8]}"
    workdir.mkdir(parents=True, exist_ok=True)
    events = workdir / "events.jsonl"
    cmd = [config.OPENCODE_BIN, "run", "--standalone", "--model", config.BRAIN_MODEL, "--format", "json"]
    for img in images:
        cmd += ["--file", str(img)]
    cmd.append(prompt + "\n\nDo not use tools. Do not read files. Answer from the attached images only.")
    # The CLI must not inherit this agent's own OpenCode/Orca session, or it
    # attaches to the caller's project and starts exploring the repo instead of
    # reading the pages.
    env = {k: v for k, v in os.environ.items() if not k.startswith(("OPENCODE", "ORCA_"))}
    with events.open("w") as fp:
        proc = subprocess.run(
            cmd, cwd=workdir, stdout=fp, stderr=subprocess.PIPE, timeout=timeout, text=True, env=env
        )
    if proc.returncode != 0:
        raise BrainError(f"brain exited {proc.returncode}: {proc.stderr[-500:]}")
    text = _event_text(events)
    if not text.strip():
        raise BrainError(f"brain returned no text (stderr: {proc.stderr[-300:]})")
    return text


def score_chapter(
    images: list[Path],
    *,
    series_title: str,
    chapter_number: str,
    chapter_title: str | None,
    page_count: int,
    motifs: list[str] | None = None,
    timeout: int = 240,
) -> dict:
    schema = json.loads(config.SCORE_SCHEMA.read_text())
    prompt = PROMPT.format(
        page_count=page_count,
        chapter_number=chapter_number,
        chapter_title=f' "{chapter_title}"' if chapter_title else "",
        chapter_title_json=json.dumps(chapter_title),
        series_title=series_title,
        motifs=", ".join(motifs or ["main", "ash", "battle", "grief", "wonder"]),
    )

    last_error = ""
    for attempt in range(3):
        try:
            if attempt == 0:
                ask = prompt
            elif last_error:
                ask = prompt + "\n\n" + REPAIR.format(error=last_error, schema=json.dumps(schema["$defs"]["section"]["properties"], indent=1)[:1500])
            else:
                ask = prompt
            raw = _run(images, ask, timeout)
            data = json.loads(_strip_fences(raw))
            _validate(data, schema, page_count)
            return data
        except subprocess.TimeoutExpired:
            last_error = ""
            continue
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = str(exc)
        except BrainError as exc:
            last_error = ""
            if "exited" in str(exc):
                continue
            raise
    raise BrainError(f"brain failed after 3 attempts: {last_error or 'timeouts'}")


def _validate(data: dict, schema: dict, page_count: int) -> None:
    import jsonschema

    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as exc:
        raise ValueError(f"{list(exc.absolute_path)}: {exc.message}") from exc

    sections = data["sections"]
    if sections[0]["start_page"] != 1:
        raise ValueError("first section must start at page 1")
    for prev, cur in zip(sections, sections[1:]):
        if cur["start_page"] != prev["end_page"] + 1:
            raise ValueError(f"gap between sections {prev['index']} and {cur['index']}")
    if sections[-1]["end_page"] != page_count:
        raise ValueError(f"last section ends at {sections[-1]['end_page']}, expected {page_count}")
