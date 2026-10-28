#!/usr/bin/env python3
"""End-to-end browser check for the reader: open a chapter, enable OST, verify a cue load.

    tools/browser-check.py <manga_id> <chapter_id>

Launches headless Chrome with the DevTools protocol, clicks "Enable OST" as a
real user gesture, and reports whether a cue was requested and played.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request

import websocket

PORT = 9333


def http(path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=10) as r:
        return json.load(r)


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: browser-check.py <manga_id> <chapter_id>")
        return 2
    manga_id, chapter_id = sys.argv[1], sys.argv[2]
    url = f"http://127.0.0.1:5173/#/c/{manga_id}/{chapter_id}"

    chrome = subprocess.Popen(
        [
            "google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu",
            "--autoplay-policy=no-user-gesture-required",
            f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
            "--window-size=1100,900", "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(40):
            try:
                http("/json/version")
                break
            except Exception:
                time.sleep(0.25)
        else:
            print("chrome did not start")
            return 1

        from urllib.parse import quote

        with urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:{PORT}/json/new?{quote(url, safe='')}", method="PUT"
            ),
            timeout=10,
        ) as r:
            target = json.load(r)

        ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30)
        seq = 0

        def call(method, params=None):
            nonlocal seq
            seq += 1
            ws.send(json.dumps({"id": seq, "method": method, "params": params or {}}))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == seq:
                    return msg

        def evaluate(expr):
            res = call("Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True})
            return res.get("result", {}).get("result", {}).get("value")

        call("Runtime.enable")
        call("Page.enable")

        for _ in range(40):
            if evaluate("document.querySelectorAll('.page img').length > 0"):
                break
            time.sleep(0.5)

        print("pages:", evaluate("document.querySelectorAll('.page img').length"))
        print("sections:", evaluate("document.querySelectorAll('.section-marker').length"))

        # real user gesture on the OST button
        clicked = evaluate(
            """(() => { const b = [...document.querySelectorAll('button')].find(x => /Enable OST|OST on/.test(x.textContent)); if (!b) return 'no-button'; b.click(); return 'clicked'; })()"""
        )
        print("ost button:", clicked)
        time.sleep(6)

        print("button now:", evaluate("document.querySelector('button.ost')?.textContent"))
        opus = evaluate(
            "performance.getEntriesByType('resource').filter(r => r.name.includes('.opus')).map(r => r.name.split('/').pop())"
        )
        print("cue requests:", opus)
        # scroll into the middle of the chapter: a different section must load
        evaluate("window.scrollTo(0, document.querySelector('.pages').scrollHeight * 0.55)")
        time.sleep(5)
        mid = evaluate(
            "performance.getEntriesByType('resource').filter(r => r.name.includes('.opus')).map(r => r.name.split('/').pop())"
        )
        print("cues after scroll:", sorted(set(mid)))
        print("active section:", evaluate("document.querySelector('.section-marker.active .sm-label')?.textContent"))
        print("now playing:", evaluate("document.querySelector('.now-label')?.textContent"))
        return 0
    finally:
        chrome.terminate()
        try:
            chrome.wait(timeout=5)
        except subprocess.TimeoutExpired:
            chrome.kill()


if __name__ == "__main__":
    raise SystemExit(main())
