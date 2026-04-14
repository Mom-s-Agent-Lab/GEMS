"""
OneIG-EN adapter — general image generation quality benchmark.

OneIG-EN provides English-language prompts covering diverse categories.
Data format: JSONL with ``{"prompt": "...", "category": "..."}`` entries.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_oneig(data_path: str) -> list[tuple[int, str, dict]]:
    """Load OneIG-EN prompts from a JSONL file."""
    items: list[tuple[int, str, dict]] = []
    path = Path(data_path)

    if not path.exists():
        raise FileNotFoundError(f"OneIG-EN data not found: {data_path}")

    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            prompt = item.get("prompt", "")
            if not prompt:
                continue
            meta = {k: v for k, v in item.items() if k != "prompt"}
            items.append((idx, prompt, meta))

    return items
