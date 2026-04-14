"""
GenEval2 adapter — compositional generation benchmark.

GenEval2 tests spatial relationships, object attributes, counting, and
complex compositions.  Data is a JSONL file with ``{"prompt": "..."}`` lines.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_geneval2(data_path: str) -> list[tuple[int, str, dict]]:
    """Load GenEval2 prompts from a JSONL file.

    Returns list of ``(index, prompt_text, metadata_dict)`` tuples.
    """
    items: list[tuple[int, str, dict]] = []
    path = Path(data_path)

    if not path.exists():
        raise FileNotFoundError(f"GenEval2 data not found: {data_path}")

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
