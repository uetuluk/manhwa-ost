#!/usr/bin/env python3
"""Validate a ChapterScore JSON against the contract and basic timeline sanity.

    tools/validate-score.py score.json [--pages 14] [--schema path]

Checks:
  * JSON Schema conformance (contracts/chapter-score.schema.json)
  * section indexes are 1..n in order
  * sections are contiguous and cover 1..page_count exactly
  * energy/tension ranges, mood vocabulary, motif vocabulary
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import jsonschema

REPO = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = REPO / "contracts" / "chapter-score.schema.json"
MOTIFS = {"main", "ash", "battle", "grief", "wonder"}


def check(score: dict, page_count: int | None) -> list[str]:
    errors: list[str] = []
    sections = score.get("sections", [])

    for i, s in enumerate(sections, start=1):
        if s.get("index") != i:
            errors.append(f"section {i}: index is {s.get('index')}, expected {i}")
        if s.get("motif") not in MOTIFS:
            errors.append(f"section {i}: unknown motif {s.get('motif')!r}")
        if s["start_page"] > s["end_page"]:
            errors.append(f"section {i}: start_page > end_page")

    if sections:
        if sections[0]["start_page"] != 1:
            errors.append(f"first section starts at {sections[0]['start_page']}, expected 1")
        for prev, cur in zip(sections, sections[1:]):
            if cur["start_page"] != prev["end_page"] + 1:
                errors.append(
                    f"gap/overlap between sections {prev['index']} and {cur['index']}: "
                    f"{prev['end_page']} -> {cur['start_page']}"
                )
        last = sections[-1]["end_page"]
        expected = page_count if page_count is not None else score.get("chapter", {}).get("page_count")
        if expected and last != expected:
            errors.append(f"last section ends at {last}, chapter has {expected} pages")

    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("score")
    ap.add_argument("--pages", type=int, default=None)
    ap.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    args = ap.parse_args()

    score = json.loads(pathlib.Path(args.score).read_text())
    schema = json.loads(pathlib.Path(args.schema).read_text())

    try:
        jsonschema.validate(score, schema)
        schema_ok = True
    except jsonschema.ValidationError as exc:
        schema_ok = False
        print(f"schema: FAIL at {list(exc.absolute_path)}: {exc.message}")
        return 1
    print("schema: ok")

    errors = check(score, args.pages)
    if errors:
        for e in errors:
            print(f"timeline: {e}")
        return 1
    print(f"timeline: ok ({len(score['sections'])} sections, pages 1..{args.pages or score['chapter']['page_count']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
