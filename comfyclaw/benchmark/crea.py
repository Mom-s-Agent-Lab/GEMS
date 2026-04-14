"""
CREA adapter — creative / artistic generation benchmark.

CREA evaluates images on 6 metrics: originality, expressiveness, aesthetic,
technical, unexpected, interpretability.  Scoring is done by a VLM judge
after image generation.
"""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

import litellm

CREA_METRICS = [
    "originality",
    "expressiveness",
    "aesthetic",
    "technical",
    "unexpected",
    "interpretability",
]

_JUDGE_SYSTEM_PROMPT = """\
You are an expert art critic and image quality evaluator. You will be shown
a generated image and the prompt that was used to create it.

Score the image on these 6 dimensions (each 0-10):
1. Originality — uniqueness and novelty of interpretation
2. Expressiveness — emotional impact and visual storytelling
3. Aesthetic — visual beauty, color harmony, composition
4. Technical — rendering quality, detail, consistency
5. Unexpected — surprise factor, creative choices
6. Interpretability — how well the image conveys the prompt's intent

Return ONLY a JSON array of 6 numbers, e.g. [8, 7, 9, 8, 6, 7].
No explanation, no other text.
"""


def load_crea(data_path: str) -> list[tuple[int, str, dict]]:
    """Load CREA prompts from a JSONL file."""
    items: list[tuple[int, str, dict]] = []
    path = Path(data_path)

    if not path.exists():
        raise FileNotFoundError(f"CREA data not found: {data_path}")

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


def evaluate_crea_image(
    image_path: str,
    prompt: str,
    model: str = "anthropic/claude-sonnet-4-5",
) -> dict[str, Any] | None:
    """Score a single image using a VLM judge on the 6 CREA metrics."""
    if not os.path.exists(image_path):
        return None

    with open(image_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode()

    try:
        resp = litellm.completion(
            model=model,
            max_tokens=256,
            messages=[
                {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                        {"type": "text", "text": f"Target Prompt: {prompt}"},
                    ],
                },
            ],
        )
        content = (resp.choices[0].message.content or "").strip()
        match = re.search(r"\[.*?\]", content, re.DOTALL)
        if match:
            scores = json.loads(match.group())
            if isinstance(scores, list) and len(scores) == 6:
                return {
                    "prompt": prompt,
                    "image_path": image_path,
                    "scores": [float(s) for s in scores],
                    "metrics": dict(zip(CREA_METRICS, [float(s) for s in scores])),
                }
    except Exception as exc:
        print(f"[CREA] Evaluation error for {image_path}: {exc}")

    return None


def evaluate_crea_batch(
    mapping: dict[str, str],
    model: str = "anthropic/claude-sonnet-4-5",
    max_workers: int = 8,
) -> dict[str, Any]:
    """Evaluate a batch of images and aggregate CREA metrics."""
    from concurrent.futures import ThreadPoolExecutor

    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(evaluate_crea_image, img_path, prompt, model)
            for prompt, img_path in mapping.items()
        ]
        for f in futures:
            res = f.result()
            if res:
                results.append(res)

    if not results:
        return {"results": [], "averages": {}, "total_score": 0.0}

    import numpy as np

    all_scores = np.array([r["scores"] for r in results])
    averages = dict(zip(CREA_METRICS, np.mean(all_scores, axis=0).tolist()))
    total = sum(averages.values())

    return {
        "results": results,
        "averages": averages,
        "total_score": total,
        "num_evaluated": len(results),
    }
