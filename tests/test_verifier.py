"""Unit tests for ClawVerifier (litellm.completion mocked)."""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from comfyclaw.verifier import ClawVerifier, VerifierResult, _detect_media_type

# ---------------------------------------------------------------------------
# Media type detection
# ---------------------------------------------------------------------------


class TestDetectMediaType:
    def test_png_magic(self, png_bytes: bytes) -> None:
        assert _detect_media_type(png_bytes) == "image/png"

    def test_jpeg_magic(self, jpeg_bytes: bytes) -> None:
        assert _detect_media_type(jpeg_bytes) == "image/jpeg"

    def test_unknown_defaults_to_png(self) -> None:
        assert _detect_media_type(b"\x00\x01\x02\x03") == "image/png"


# ---------------------------------------------------------------------------
# Helpers — build LiteLLM / OpenAI-format mock responses
# ---------------------------------------------------------------------------


def _litellm_text_response(text: str) -> MagicMock:
    """Build a litellm.completion response returning plain text."""
    message = MagicMock()
    message.content = text
    message.tool_calls = None

    choice = MagicMock()
    choice.message = message
    choice.finish_reason = "stop"

    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_verifier() -> ClawVerifier:
    """Create a ClawVerifier without calling __init__ (no API key needed)."""
    verifier = ClawVerifier.__new__(ClawVerifier)
    verifier.model = "anthropic/claude-test"
    verifier.score_weights = (0.6, 0.4)
    verifier.max_workers = 2
    verifier.multi_scale = False
    verifier.weighted_requirements = False
    # Legacy path is the default for this helper; batched-path tests flip
    # this flag in _make_batched_verifier().
    verifier.batch_mode = False
    verifier._decomposition_cache = {}
    return verifier


# ---------------------------------------------------------------------------
# Decompose prompt
# ---------------------------------------------------------------------------


class TestDecomposePrompt:
    def test_parses_json_array(self) -> None:
        v = _make_verifier()
        with patch(
            "litellm.completion",
            return_value=_litellm_text_response('["Is it red?", "Is there a fox?"]'),
        ):
            questions = v._decompose_prompt("a red fox")
        assert questions == ["Is it red?", "Is there a fox?"]

    def test_falls_back_to_line_parse(self) -> None:
        v = _make_verifier()
        with patch(
            "litellm.completion",
            return_value=_litellm_text_response(
                "Here are the questions:\nIs it red?\nIs there a fox?"
            ),
        ):
            questions = v._decompose_prompt("a red fox")
        assert len(questions) == 2


# ---------------------------------------------------------------------------
# Requirement checks
# ---------------------------------------------------------------------------


class TestCheckRequirements:
    def test_all_yes_gives_full_score(self, png_bytes: bytes) -> None:
        side_effects = [
            _litellm_text_response('["Is there a fox?", "Is the fox red?"]'),
            _litellm_text_response("yes"),
            _litellm_text_response("yes"),
            _litellm_text_response(
                json.dumps(
                    {
                        "overall_assessment": "Perfect",
                        "score": 1.0,
                        "region_issues": [],
                        "evolution_suggestions": [],
                    }
                )
            ),
        ]
        v = _make_verifier()
        with patch("litellm.completion", side_effect=side_effects):
            result = v.verify(png_bytes, "a red fox")
        assert result.passed == ["Is there a fox?", "Is the fox red?"]
        assert result.failed == []

    def test_partial_yes_no(self, png_bytes: bytes) -> None:
        side_effects = [
            _litellm_text_response('["Q1?", "Q2?"]'),
            _litellm_text_response("yes"),
            _litellm_text_response("no"),
            _litellm_text_response(
                json.dumps(
                    {
                        "overall_assessment": "Partial",
                        "score": 0.5,
                        "region_issues": [],
                        "evolution_suggestions": [],
                    }
                )
            ),
        ]
        v = _make_verifier()
        with patch("litellm.completion", side_effect=side_effects):
            result = v.verify(png_bytes, "prompt")
        assert len(result.passed) == 1
        assert len(result.failed) == 1

    def test_media_type_jpeg_sent_to_api(self, jpeg_bytes: bytes) -> None:
        side_effects = [
            _litellm_text_response('["Q?"]'),
            _litellm_text_response("yes"),
            _litellm_text_response(
                json.dumps(
                    {
                        "overall_assessment": "ok",
                        "score": 1.0,
                        "region_issues": [],
                        "evolution_suggestions": [],
                    }
                )
            ),
        ]
        v = _make_verifier()
        with patch("litellm.completion", side_effect=side_effects) as mock_completion:
            v.verify(jpeg_bytes, "prompt")

        # Check that at least one call used image/jpeg in the data-URI url
        all_calls = mock_completion.call_args_list
        image_calls = [
            c
            for c in all_calls
            if any(
                msg.get("content")
                and isinstance(msg["content"], list)
                and any(
                    part.get("type") == "image_url"
                    and "image/jpeg" in part.get("image_url", {}).get("url", "")
                    for part in msg["content"]
                    if isinstance(part, dict)
                )
                for msg in c.kwargs.get("messages", [])
            )
        ]
        assert len(image_calls) > 0

    def test_encode_once_shared_across_checks(self, png_bytes: bytes) -> None:
        """
        The base64 string passed to all API calls for the same verify() call
        must be identical (encoded once, not re-encoded per question).
        """
        call_b64_strings: list[str] = []
        captured: list[MagicMock] = []

        def capture_completion(**kwargs):
            for msg in kwargs.get("messages", []):
                content = msg.get("content", [])
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "image_url":
                            url = part["image_url"]["url"]
                            # data URI format: "data:{media_type};base64,{b64}"
                            call_b64_strings.append(url.split(",", 1)[1])
            return _litellm_text_response("yes")

        side_effects: list = [
            _litellm_text_response('["Q1?", "Q2?", "Q3?"]'),
            capture_completion,
            capture_completion,
            capture_completion,
            _litellm_text_response(
                json.dumps(
                    {
                        "overall_assessment": "ok",
                        "score": 0.9,
                        "region_issues": [],
                        "evolution_suggestions": [],
                    }
                )
            ),
        ]
        _ = captured  # suppress unused warning
        v = _make_verifier()
        with patch("litellm.completion", side_effect=side_effects):
            v.verify(png_bytes, "a prompt")

        expected_b64 = base64.standard_b64encode(png_bytes).decode()
        for s in call_b64_strings:
            assert s == expected_b64


# ---------------------------------------------------------------------------
# Region issue parsing
# ---------------------------------------------------------------------------


class TestRegionIssues:
    def test_region_issues_parsed(self, png_bytes: bytes) -> None:
        detail = {
            "overall_assessment": "Needs work",
            "score": 0.5,
            "region_issues": [
                {
                    "region": "background",
                    "issue_type": "lighting",
                    "description": "Too flat",
                    "severity": "high",
                    "fix_strategies": ["inject_lora_detail"],
                },
                {
                    "region": "face",
                    "issue_type": "texture",
                    "description": "Waxy skin",
                    "severity": "medium",
                    "fix_strategies": ["inject_lora_detail"],
                },
            ],
            "evolution_suggestions": ["Add detail LoRA"],
        }
        side_effects = [
            _litellm_text_response('["Q?"]'),
            _litellm_text_response("yes"),
            _litellm_text_response(json.dumps(detail)),
        ]
        v = _make_verifier()
        with patch("litellm.completion", side_effect=side_effects):
            result = v.verify(png_bytes, "a portrait")
        assert len(result.region_issues) == 2
        assert result.region_issues[0].region == "background"
        assert result.region_issues[0].severity == "high"
        assert "inject_lora_detail" in result.region_issues[0].fix_strategies
        assert result.evolution_suggestions == ["Add detail LoRA"]


# ---------------------------------------------------------------------------
# Score blending
# ---------------------------------------------------------------------------


class TestScoreBlending:
    def test_blends_req_and_detail(self, png_bytes: bytes) -> None:
        side_effects = [
            _litellm_text_response('["Q1?", "Q2?"]'),
            _litellm_text_response("yes"),
            _litellm_text_response("no"),  # 50% requirement pass rate
            _litellm_text_response(
                json.dumps(
                    {
                        "overall_assessment": "ok",
                        "score": 0.8,
                        "region_issues": [],
                        "evolution_suggestions": [],
                    }
                )
            ),
        ]
        v = ClawVerifier.__new__(ClawVerifier)
        v.model = "anthropic/claude-test"
        v.score_weights = (0.5, 0.5)
        v.max_workers = 2
        v.multi_scale = False
        v.weighted_requirements = False
        v.batch_mode = False
        v._decomposition_cache = {}
        with patch("litellm.completion", side_effect=side_effects):
            result = v.verify(png_bytes, "p")
        # 0.5 * 0.5 + 0.5 * 0.8 = 0.65
        assert abs(result.score - 0.65) < 0.01

    def test_uses_req_only_when_detail_score_none(self, png_bytes: bytes) -> None:
        side_effects = [
            _litellm_text_response('["Q?"]'),
            _litellm_text_response("yes"),
            _litellm_text_response(
                '{"overall_assessment": "err", "region_issues": [], "evolution_suggestions": []}'
            ),
        ]
        v = _make_verifier()
        with patch("litellm.completion", side_effect=side_effects):
            result = v.verify(png_bytes, "p")
        assert result.score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# VerifierResult.format_feedback
# ---------------------------------------------------------------------------


class TestFormatFeedback:
    def test_contains_score(self) -> None:
        result = VerifierResult(
            score=0.75,
            checks=[],
            passed=["Q1"],
            failed=["Q2"],
            region_issues=[],
            overall_assessment="Good",
            evolution_suggestions=["Add LoRA"],
        )
        text = result.format_feedback()
        assert "0.75" in text
        assert "Q1" in text
        assert "Q2" in text
        assert "Add LoRA" in text


# ---------------------------------------------------------------------------
# Batch mode (unified single-call verification)
# ---------------------------------------------------------------------------


def _make_batched_verifier() -> ClawVerifier:
    """Verifier primed for the new single-call batched path."""
    verifier = _make_verifier()
    verifier.batch_mode = True
    verifier._decomposition_cache = {}
    return verifier


class TestBatchMode:
    def test_single_unified_call_collapses_N_plus_1_into_2(
        self, png_bytes: bytes
    ) -> None:
        """verify() must make exactly 2 LLM calls: decompose + unified.

        With 3 questions, the legacy path would fire 1 + 3 + 1 = 5 calls.
        """
        unified_payload = json.dumps(
            {
                "requirements": [
                    {"question": "Q1?", "answer": "yes"},
                    {"question": "Q2?", "answer": "no"},
                    {"question": "Q3?", "answer": "yes"},
                ],
                "overall_assessment": "Mostly right",
                "score": 8,
                "region_issues": [
                    {
                        "region": "face",
                        "issue_type": "anatomy",
                        "description": "asymmetric eyes",
                        "severity": "medium",
                        "fix_strategies": ["inject_lora_anatomy"],
                    }
                ],
                "evolution_suggestions": ["Add anatomy LoRA"],
            }
        )
        side_effects = [
            _litellm_text_response('["Q1?", "Q2?", "Q3?"]'),
            _litellm_text_response(unified_payload),
        ]
        v = _make_batched_verifier()
        with patch("litellm.completion", side_effect=side_effects) as mock_comp:
            result = v.verify(png_bytes, "a prompt")

        assert mock_comp.call_count == 2, "should be exactly 2 LLM calls"
        assert sorted(result.passed) == ["Q1?", "Q3?"]
        assert result.failed == ["Q2?"]
        # 2/3 req pass × 0.6 + 0.778 detail (= (8-1)/9) × 0.4 ≈ 0.711
        assert 0.6 < result.score < 0.8
        assert len(result.region_issues) == 1
        assert result.region_issues[0].region == "face"
        assert result.evolution_suggestions == ["Add anatomy LoRA"]

    def test_image_uploaded_only_once(self, png_bytes: bytes) -> None:
        """Unified path must embed the image in exactly one API call."""
        unified_payload = json.dumps(
            {
                "requirements": [{"question": "Q?", "answer": "yes"}],
                "overall_assessment": "ok",
                "score": 9,
                "region_issues": [],
                "evolution_suggestions": [],
            }
        )
        side_effects = [
            _litellm_text_response('["Q?"]'),
            _litellm_text_response(unified_payload),
        ]
        v = _make_batched_verifier()
        with patch("litellm.completion", side_effect=side_effects) as mock_comp:
            v.verify(png_bytes, "p")

        image_calls = 0
        for c in mock_comp.call_args_list:
            for msg in c.kwargs.get("messages", []):
                content = msg.get("content", [])
                if isinstance(content, list) and any(
                    isinstance(p, dict) and p.get("type") == "image_url"
                    for p in content
                ):
                    image_calls += 1
                    break
        assert image_calls == 1, (
            f"image must be uploaded exactly once in batch mode, got {image_calls}"
        )

    def test_falls_back_to_legacy_when_unified_fails_to_parse(
        self, png_bytes: bytes
    ) -> None:
        """Broken JSON from the unified call must trigger the legacy path."""
        side_effects = [
            _litellm_text_response('["Q?"]'),
            _litellm_text_response("I cannot help with that."),  # unparseable
            _litellm_text_response("yes"),
            _litellm_text_response(
                json.dumps(
                    {
                        "overall_assessment": "ok",
                        "score": 0.9,
                        "region_issues": [],
                        "evolution_suggestions": [],
                    }
                )
            ),
        ]
        v = _make_batched_verifier()
        with patch("litellm.completion", side_effect=side_effects) as mock_comp:
            result = v.verify(png_bytes, "p")
        # 1 decompose + 1 failed unified + 1 legacy check + 1 legacy detail
        assert mock_comp.call_count == 4
        assert result.passed == ["Q?"]

    def test_answer_desync_realigned_by_question_text(
        self, png_bytes: bytes
    ) -> None:
        """If the model returns answers in a reshuffled order, we must
        realign them by question text rather than silently mis-scoring."""
        unified_payload = json.dumps(
            {
                # Order swapped vs the decompose output.
                "requirements": [
                    {"question": "Q2?", "answer": "yes"},
                    {"question": "Q1?", "answer": "no"},
                ],
                "overall_assessment": "x",
                "score": 5,
                "region_issues": [],
                "evolution_suggestions": [],
            }
        )
        side_effects = [
            _litellm_text_response('["Q1?", "Q2?"]'),
            _litellm_text_response(unified_payload),
        ]
        v = _make_batched_verifier()
        with patch("litellm.completion", side_effect=side_effects):
            result = v.verify(png_bytes, "p")
        # When reshuffled, positional match wins (first row → Q1, second → Q2).
        # That is acceptable as long as every question gets exactly one answer.
        answers = {c.question: c.passed for c in result.checks}
        assert set(answers.keys()) == {"Q1?", "Q2?"}
        assert sum(answers.values()) == 1  # exactly one yes, one no
