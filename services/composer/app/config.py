from __future__ import annotations

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("MANHWA_OST_DATA", "/srv/manhwa-ost"))
LIBRARY_DIR = Path(os.environ.get("OST_LIBRARY", DATA_DIR / "library"))
CACHE_DIR = Path(os.environ.get("OST_CACHE", DATA_DIR / "cache"))
RUN_DIR = Path(os.environ.get("OST_RUN_DIR", DATA_DIR / "run"))

REPO_DIR = Path(__file__).resolve().parents[3]
CONTRACTS_DIR = REPO_DIR / "contracts"
SCORE_SCHEMA = CONTRACTS_DIR / "chapter-score.schema.json"

AUDIOCPP_CLI = Path(os.environ.get("AUDIOCPP_CLI", DATA_DIR / "build/yue2/bin/audiocpp_cli"))
YUE2_MODEL_ROOT = Path(os.environ.get("YUE2_MODEL_ROOT", "/srv/models/yue2"))
YUE2_AR_LORA = os.environ.get("YUE2_AR_LORA", "adapters/ar_lora_inst_v3abc.bf16.safetensors")

OPENCODE_BIN = os.environ.get("OPENCODE_BIN", "opencode")
BRAIN_MODEL = os.environ.get("BRAIN_MODEL", "opencode-go/deepseek-v4.1-flash")

DEFAULT_ABC = CONTRACTS_DIR / "abc" / "ashen-crown.abc"

# 25 semantic frames per second of generated audio.
FRAMES_PER_SECOND = 25
CUE_SECONDS = 50

for d in (LIBRARY_DIR, CACHE_DIR, RUN_DIR):
    d.mkdir(parents=True, exist_ok=True)
