"""
Verifier utilities — region cropping, score calibration, requirement weighting,
and comparative verification support.
"""

from __future__ import annotations

import base64
import io
import json
import math
import re
from typing import Any

from PIL import Image

# ── Region cropping ──────────────────────────────────────────────────────

# Predefined crop regions as (x_frac, y_frac, w_frac, h_frac) in [0,1]
STANDARD_REGIONS: dict[str, tuple[float, float, float, float]] = {
    "full": (0.0, 0.0, 1.0, 1.0),
    "upper_half": (0.0, 0.0, 1.0, 0.5),
    "lower_half": (0.0, 0.5, 1.0, 0.5),
    "left_half": (0.0, 0.0, 0.5, 1.0),
    "right_half": (0.5, 0.0, 0.5, 1.0),
    "center": (0.25, 0.25, 0.5, 0.5),
    "face_region": (0.25, 0.05, 0.5, 0.35),
    "hands_region": (0.15, 0.45, 0.7, 0.35),
    "background": (0.0, 0.0, 1.0, 0.4),
    "foreground": (0.1, 0.5, 0.8, 0.5),
}


def crop_region(
    image_bytes: bytes,
    region: str | tuple[float, float, float, float],
) -> bytes:
    """Crop a named or custom region from the image.

    Parameters
    ----------
    image_bytes : Raw PNG/JPEG bytes.
    region : Either a name from ``STANDARD_REGIONS`` or a tuple of
             ``(x_frac, y_frac, w_frac, h_frac)`` in ``[0, 1]``.

    Returns
    -------
    Cropped image as PNG bytes.
    """
    if isinstance(region, str):
        if region not in STANDARD_REGIONS:
            raise ValueError(f"Unknown region: {region!r}. Known: {list(STANDARD_REGIONS)}")
        x_f, y_f, w_f, h_f = STANDARD_REGIONS[region]
    else:
        x_f, y_f, w_f, h_f = region

    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size
    left = int(x_f * w)
    upper = int(y_f * h)
    right = int((x_f + w_f) * w)
    lower = int((y_f + h_f) * h)

    cropped = img.crop((left, upper, right, lower))
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    return buf.getvalue()


def encode_image_b64(image_bytes: bytes) -> str:
    """Encode raw image bytes to base64 string."""
    return base64.standard_b64encode(image_bytes).decode()


# ── Requirement weighting ────────────────────────────────────────────────

# Keywords that signal high-importance requirements
HIGH_WEIGHT_SIGNALS = {
    "photorealistic", "realistic", "accurate", "exact", "precise",
    "must", "critical", "important", "specific", "correct",
    "human", "face", "hands", "fingers", "eyes", "anatomy",
    "text", "sign", "writing", "letters", "words",
    "count", "number", "quantity",
}

MEDIUM_WEIGHT_SIGNALS = {
    "style", "color", "lighting", "composition", "mood",
    "background", "foreground", "position", "layout",
    "detailed", "quality", "sharp", "clear",
}


def compute_requirement_weight(question: str) -> float:
    """Assign a weight (0.5 – 2.0) to a verification question based on
    how important the requirement is likely to be.
    """
    q_lower = question.lower()
    words = set(re.findall(r"[a-z]+", q_lower))

    if words & HIGH_WEIGHT_SIGNALS:
        return 1.5
    if words & MEDIUM_WEIGHT_SIGNALS:
        return 1.0
    return 0.75


def weighted_requirement_score(
    questions: list[str],
    passed: list[bool],
) -> float:
    """Compute a weighted pass rate across requirements."""
    if not questions:
        return 0.0

    total_weight = 0.0
    passed_weight = 0.0
    for q, p in zip(questions, passed):
        w = compute_requirement_weight(q)
        total_weight += w
        if p:
            passed_weight += w

    return passed_weight / total_weight if total_weight > 0 else 0.0


# ── Score calibration ────────────────────────────────────────────────────


class ScoreCalibrator:
    """Track score distribution and provide normalized scores.

    As the system runs more prompts, the calibrator learns the
    typical score range and normalizes new scores to [0, 1].
    """

    def __init__(self) -> None:
        self._scores: list[float] = []
        self._running_mean: float = 0.5
        self._running_var: float = 0.04  # initial assumption: std=0.2

    def record(self, score: float) -> None:
        """Record a new raw score."""
        self._scores.append(score)
        n = len(self._scores)
        if n >= 3:
            self._running_mean = sum(self._scores) / n
            self._running_var = sum(
                (s - self._running_mean) ** 2 for s in self._scores
            ) / n

    def calibrate(self, raw_score: float) -> float:
        """Normalize a raw score based on the observed distribution.

        Uses a z-score transformation mapped to [0, 1] via sigmoid.
        """
        std = math.sqrt(self._running_var) if self._running_var > 0 else 0.2
        z = (raw_score - self._running_mean) / std
        calibrated = 1.0 / (1.0 + math.exp(-z))
        return max(0.0, min(1.0, calibrated))

    @property
    def stats(self) -> dict[str, float]:
        return {
            "mean": self._running_mean,
            "std": math.sqrt(self._running_var),
            "n_samples": len(self._scores),
        }


# ── Comparative verification ─────────────────────────────────────────────

_COMPARATIVE_PROMPT = """\
You are an expert image quality judge. You will see two images generated from
the same prompt. Compare them and determine which is better.

Prompt: {prompt}

Respond with a JSON object:
{{
  "winner": "A" or "B",
  "confidence": <0.0-1.0>,
  "reason": "<1-2 sentence explanation>",
  "a_strengths": ["<strength1>", "<strength2>"],
  "a_weaknesses": ["<weakness1>"],
  "b_strengths": ["<strength1>", "<strength2>"],
  "b_weaknesses": ["<weakness1>"]
}}
"""


def build_comparative_message(
    image_a_b64: str,
    image_b_b64: str,
    prompt: str,
    media_type: str = "image/png",
) -> list[dict[str, Any]]:
    """Build the messages list for a comparative verification call."""
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{image_a_b64}"},
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{image_b_b64}"},
                },
                {
                    "type": "text",
                    "text": _COMPARATIVE_PROMPT.format(prompt=prompt),
                },
            ],
        }
    ]


def parse_comparative_result(response_text: str) -> dict[str, Any]:
    """Parse the JSON response from a comparative verification call."""
    try:
        m = re.search(r"\{.*\}", response_text, re.DOTALL)
        if m:
            return json.loads(m.group())
    except (json.JSONDecodeError, AttributeError):
        pass
    return {"winner": "A", "confidence": 0.5, "reason": "Parse error"}
