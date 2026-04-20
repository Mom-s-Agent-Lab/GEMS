"""Phase 1 fixes — B1 clamp, B2 orphan-prune, B3 iter-refund, B5 baseline cache.

See ``canvases/comfyclaw-pipeline-review.canvas.tsx`` for the motivation:
these four changes collectively eliminated ~50% of pre-flight validation
rejections and ~340s of redundant baseline generation per 10-prompt run.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from comfyclaw.agent import ClawAgent
from comfyclaw.agent import _TOOLS as TOOLS
from comfyclaw.harness import (
    ClawHarness,
    HarnessConfig,
    _BaselineCache,
    _baseline_cache_key,
    _verifier_result_from_json,
    _verifier_result_to_json,
)
from comfyclaw.verifier import RegionIssue, RequirementCheck, VerifierResult
from comfyclaw.workflow import WorkflowManager


# Reuse the same fixtures as test_harness.py
from tests.test_harness import (  # noqa: E402  – intentional cross-module import
    _make_harness,
    _mock_agent,
    _mock_verifier,
)


# ---------------------------------------------------------------------------
# B1 — foreground_weight default/clamp + schema min/max
# ---------------------------------------------------------------------------


class TestB1ForegroundWeightClamp:
    """``add_regional_attention`` used to default ``foreground_weight=1.3`` which
    ComfyUI's ``ConditioningAverage.conditioning_to_strength`` rejects
    (max=1.0).  This covered ~50% of all pre-flight validation failures in
    the 10-prompt GenEval2 runs."""

    def _regional_tool_schema(self) -> dict:
        for t in TOOLS:
            if t["function"]["name"] == "add_regional_attention":
                return t["function"]["parameters"]
        raise AssertionError("add_regional_attention tool not found")

    def test_schema_declares_range_and_default(self) -> None:
        schema = self._regional_tool_schema()
        fw = schema["properties"]["foreground_weight"]
        assert fw["type"] == "number"
        assert fw["minimum"] == 0.0
        assert fw["maximum"] == 1.0
        assert fw["default"] == 1.0, (
            "Default must be <= ComfyUI's max (1.0); historic 1.3 caused "
            "prompt_outputs_failed_validation."
        )

    def test_tool_description_warns_about_comfyui_clamp(self) -> None:
        for t in TOOLS:
            if t["function"]["name"] == "add_regional_attention":
                desc = t["function"]["description"]
                break
        else:
            raise AssertionError
        assert "1.0" in desc
        assert "conditioning_to_strength" in desc
        assert "prompt_outputs_failed_validation" in desc

    def _run_regional_on_minimal_workflow(self, fg_weight: float | None) -> WorkflowManager:
        """Invoke ``_add_regional_attention`` on a pre-wired workflow and
        return the resulting WorkflowManager."""
        wm = WorkflowManager(
            {
                "1": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "x.ckpt"},
                },
                "2": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"clip": ["1", 1], "text": "fox"},
                },
                "3": {
                    "class_type": "KSampler",
                    "inputs": {"model": ["1", 0], "positive": ["2", 0]},
                },
            }
        )

        agent = ClawAgent.__new__(ClawAgent)
        agent._notify = lambda _wm: None  # type: ignore[attr-defined]
        inputs: dict = {
            "positive_node_id": "2",
            "clip_node_id": "1",
            "foreground_prompt": "a red fox",
            "background_prompt": "forest",
        }
        if fg_weight is not None:
            inputs["foreground_weight"] = fg_weight
        agent._add_regional_attention(wm, inputs)
        return wm

    def _avg_strength(self, wm: WorkflowManager) -> float:
        for node in wm.workflow.values():
            if node.get("class_type") == "ConditioningAverage":
                return node["inputs"]["conditioning_to_strength"]
        raise AssertionError("ConditioningAverage node not found")

    def test_default_weight_is_one(self) -> None:
        wm = self._run_regional_on_minimal_workflow(fg_weight=None)
        assert self._avg_strength(wm) == 1.0

    def test_weight_above_one_is_clamped(self) -> None:
        wm = self._run_regional_on_minimal_workflow(fg_weight=1.3)
        assert self._avg_strength(wm) == 1.0, (
            "Agent-supplied 1.3 must be clamped; otherwise ComfyUI replies "
            "'Value 1.3 bigger than max of 1.0' and rejects the workflow."
        )

    def test_weight_below_zero_is_clamped(self) -> None:
        wm = self._run_regional_on_minimal_workflow(fg_weight=-0.5)
        assert self._avg_strength(wm) == 0.0

    def test_weight_in_range_is_preserved(self) -> None:
        wm = self._run_regional_on_minimal_workflow(fg_weight=0.7)
        assert self._avg_strength(wm) == 0.7


# ---------------------------------------------------------------------------
# B2 — orphan conditioning prune
# ---------------------------------------------------------------------------


class TestB2OrphanConditioningPrune:
    """Structural edits (regional-control, hires-fix re-wiring) leave the old
    CLIPTextEncode / Conditioning* subgraph with no downstream consumer.
    ComfyUI still walks those nodes and raises
    ``exception_during_inner_validation`` for broken refs inside the island,
    killing the whole submission.  The pruner removes them pre-submit."""

    def test_orphan_text_encoder_is_pruned(self) -> None:
        wf = {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "a"}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "b"}},
            "4": {
                "class_type": "KSampler",
                # Only node 3 is consumed -> node 2 is an orphan.
                "inputs": {"model": ["1", 0], "positive": ["3", 0]},
            },
        }
        removed = WorkflowManager.prune_orphan_conditioning(wf)
        assert "2" not in wf
        assert "3" in wf
        assert len(removed) == 1
        assert "[2]" in removed[0]

    def test_iterative_prune_collapses_chains(self) -> None:
        """Pruning node N can make N's own upstream conditioning node orphan
        too — the loop keeps going until stable."""
        wf = {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "a"}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "b"}},
            "4": {
                "class_type": "ConditioningAverage",
                "inputs": {
                    "conditioning_to": ["2", 0],
                    "conditioning_from": ["3", 0],
                    "conditioning_to_strength": 0.7,
                },
            },
            # Node 5 is a text encoder that's used by sampler; 4 above is
            # dangling (no downstream user).
            "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "c"}},
            "6": {
                "class_type": "KSampler",
                "inputs": {"model": ["1", 0], "positive": ["5", 0]},
            },
        }
        removed = WorkflowManager.prune_orphan_conditioning(wf)
        assert "4" not in wf  # average orphan -> pruned first pass
        # Nodes 2 and 3 only fed node 4; after it's gone they become orphan too.
        assert "2" not in wf
        assert "3" not in wf
        assert "5" in wf and "6" in wf
        assert len(removed) == 3

    def test_reachable_conditioning_stays(self) -> None:
        wf = {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "a"}},
            "3": {
                "class_type": "KSampler",
                "inputs": {"model": ["1", 0], "positive": ["2", 0]},
            },
        }
        removed = WorkflowManager.prune_orphan_conditioning(wf)
        assert removed == []
        assert "2" in wf

    def test_loaders_and_samplers_are_never_pruned(self) -> None:
        """Even if nothing references them, loaders/samplers/VAEDecode/SaveImage
        stay — they're not in the conditioning-family allowlist."""
        wf = {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
            "2": {"class_type": "VAELoader", "inputs": {}},
        }
        removed = WorkflowManager.prune_orphan_conditioning(wf)
        assert removed == []
        assert "1" in wf and "2" in wf

    def test_dangling_inbound_links_are_scrubbed(self) -> None:
        """After pruning an orphan, no surviving node should still reference
        its node id — otherwise ComfyUI would trip over the dangling link."""
        wf = {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {"clip": ["1", 1], "text": "a", "unused_upstream": ["999", 0]},
            },
            # A loose dict that references an orphan we're about to prune
            "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "b"}},
            "4": {
                "class_type": "KSampler",
                # Only 3 is consumed.
                "inputs": {"model": ["1", 0], "positive": ["3", 0]},
            },
        }
        WorkflowManager.prune_orphan_conditioning(wf)
        # Node 2 should be gone; make sure no surviving input still points at "2".
        for node in wf.values():
            for v in node.get("inputs", {}).values():
                if isinstance(v, list) and len(v) == 2:
                    assert str(v[0]) != "2"

    def test_empty_workflow_is_noop(self) -> None:
        removed = WorkflowManager.prune_orphan_conditioning({})
        assert removed == []


# ---------------------------------------------------------------------------
# B3 — non-productive iteration budget refund
# ---------------------------------------------------------------------------


class TestB3IterationBudgetRefund:
    """Iterations that never make it past ComfyUI's pre-flight validator do not
    consume the ``max_iterations`` budget — they're tracked separately under
    ``max_extra_agent_invocations``."""

    @pytest.fixture()
    def cfg(self) -> HarnessConfig:
        return HarnessConfig(
            api_key="sk-ant-test",
            server_address="127.0.0.1:9999",
            max_iterations=2,
            sync_port=0,
            evolve_from_best=True,
        )

    def test_non_productive_iter_gets_refunded(
        self, minimal_workflow: dict, cfg: HarnessConfig
    ) -> None:
        """First two submits fail validation (no prompt_id), third succeeds.
        With max_iterations=1 and max_extra_agent_invocations=2, the agent
        should still produce a final image on attempt 3 because the first
        two non-productive iters were refunded."""
        image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        mock_client = MagicMock()
        # attempts: (queue + 2 repairs) × 3 iter-rounds = 9 queue calls.
        # We make the first 2 iter-rounds (6 calls) all fail, then the 7th
        # (the first submit of iter-round 3) succeed.
        side_effects: list = [Exception("validation err")] * 6
        side_effects.append({"prompt_id": "pid-ok"})
        mock_client.queue_prompt.side_effect = side_effects
        mock_client.wait_for_completion.return_value = {
            "outputs": {"7": {"images": [{"filename": "t.png", "subfolder": "", "type": "output"}]}}
        }
        mock_client.collect_images.return_value = [image]

        cfg.max_iterations = 1
        cfg.max_repair_attempts = 2
        cfg.max_extra_agent_invocations = 2
        h = _make_harness(minimal_workflow, cfg, client=mock_client)
        result = h.run("test prompt")

        assert result == image, "Refund should have let us reach a successful submit."

    def test_refund_is_capped_by_max_extra(
        self, minimal_workflow: dict, cfg: HarnessConfig
    ) -> None:
        """If validation keeps failing, the run bails after
        ``max_extra_agent_invocations`` refunds — does NOT loop forever."""
        mock_client = MagicMock()
        mock_client.queue_prompt.side_effect = Exception("persistent validation err")

        cfg.max_iterations = 1
        cfg.max_repair_attempts = 1
        cfg.max_extra_agent_invocations = 2
        h = _make_harness(minimal_workflow, cfg, client=mock_client)
        result = h.run("test")

        assert result is None
        # Queue was called across (1 initial + max_extra=2 refunded) = 3
        # iter-rounds, each doing (1 submit + 1 repair) = 2 queue calls.
        # After the 3rd round the extra-counter hits max+1 and we bail.
        assert mock_client.queue_prompt.call_count == 3 * 2

    def test_opt_out_with_zero_extra(
        self, minimal_workflow: dict, cfg: HarnessConfig
    ) -> None:
        """max_extra_agent_invocations=0 preserves the pre-B3 behaviour: a
        single pass of (1 initial + max_repair_attempts) submits, then bail."""
        mock_client = MagicMock()
        mock_client.queue_prompt.side_effect = Exception("err")

        cfg.max_iterations = 1
        cfg.max_repair_attempts = 1
        cfg.max_extra_agent_invocations = 0
        h = _make_harness(minimal_workflow, cfg, client=mock_client)
        h.run("test")

        # Exactly (1 + 1) = 2 submits, no refund.
        assert mock_client.queue_prompt.call_count == 2


# ---------------------------------------------------------------------------
# B5 — baseline cache
# ---------------------------------------------------------------------------


class TestB5BaselineCacheHelpers:
    def test_key_is_deterministic(self) -> None:
        wf = {"1": {"class_type": "X", "inputs": {"a": 1, "b": 2}}}
        k1 = _baseline_cache_key(wf, "fox", "longcat-image")
        k2 = _baseline_cache_key(wf, "fox", "longcat-image")
        assert k1 == k2
        assert len(k1) == 64  # sha256 hex

    def test_key_differs_on_prompt_change(self) -> None:
        wf = {"1": {"class_type": "X", "inputs": {}}}
        assert _baseline_cache_key(wf, "fox", None) != _baseline_cache_key(wf, "dog", None)

    def test_key_differs_on_workflow_change(self) -> None:
        wf_a = {"1": {"class_type": "X", "inputs": {}}}
        wf_b = {"1": {"class_type": "Y", "inputs": {}}}
        assert _baseline_cache_key(wf_a, "fox", None) != _baseline_cache_key(wf_b, "fox", None)

    def test_key_differs_on_image_model_change(self) -> None:
        wf = {"1": {"class_type": "X", "inputs": {}}}
        assert _baseline_cache_key(wf, "fox", "longcat") != _baseline_cache_key(wf, "fox", "qwen")

    def test_key_stable_under_dict_order(self) -> None:
        wf_a = {"1": {"class_type": "X", "inputs": {"a": 1, "b": 2}}}
        wf_b = {"1": {"inputs": {"b": 2, "a": 1}, "class_type": "X"}}
        assert _baseline_cache_key(wf_a, "fox", None) == _baseline_cache_key(wf_b, "fox", None)

    def test_verifier_result_roundtrip(self) -> None:
        vr = VerifierResult(
            score=0.72,
            checks=[RequirementCheck("Q1?", "yes", True)],
            passed=["has fox"],
            failed=["has hat"],
            region_issues=[
                RegionIssue(
                    region="background",
                    issue_type="texture",
                    description="blurry",
                    severity="low",
                    fix_strategies=["hires fix"],
                )
            ],
            overall_assessment="ok",
            evolution_suggestions=["try regional"],
            feedback_source="vlm",
        )
        restored = _verifier_result_from_json(_verifier_result_to_json(vr))
        assert restored is not None
        assert restored.score == 0.72
        assert restored.passed == ["has fox"]
        assert restored.failed == ["has hat"]
        assert len(restored.checks) == 1
        assert restored.checks[0].passed is True
        assert restored.region_issues[0].region == "background"
        assert restored.evolution_suggestions == ["try regional"]

    def test_verifier_roundtrip_handles_none(self) -> None:
        assert _verifier_result_to_json(None) is None
        assert _verifier_result_from_json(None) is None
        assert _verifier_result_from_json({}) is None


class TestB5BaselineCacheDisk:
    def test_store_then_lookup_returns_image_and_vr(self, tmp_path: Path) -> None:
        cache = _BaselineCache(tmp_path)
        key = "abc123"
        img = b"PNGBYTES" * 10
        vr = VerifierResult(
            score=0.9,
            checks=[],
            passed=["all good"],
            failed=[],
        )
        cache.store(key, img, vr, prompt="fox", image_model="longcat")

        hit = cache.lookup(key)
        assert hit is not None
        restored_img, restored_vr = hit
        assert restored_img == img
        assert restored_vr is not None
        assert restored_vr.score == 0.9
        assert restored_vr.passed == ["all good"]

    def test_lookup_missing_key_returns_none(self, tmp_path: Path) -> None:
        cache = _BaselineCache(tmp_path)
        assert cache.lookup("nothing") is None

    def test_lookup_missing_webp_or_json_returns_none(self, tmp_path: Path) -> None:
        cache = _BaselineCache(tmp_path)
        # Only the .json exists.
        (tmp_path / "k.json").write_text(json.dumps({"verifier": None}))
        assert cache.lookup("k") is None

        # Only the .webp exists.
        (tmp_path / "j.webp").write_bytes(b"x")
        assert cache.lookup("j") is None

    def test_corrupt_json_is_treated_as_miss(self, tmp_path: Path) -> None:
        cache = _BaselineCache(tmp_path)
        (tmp_path / "k.webp").write_bytes(b"x")
        (tmp_path / "k.json").write_text("not valid json {{")
        assert cache.lookup("k") is None

    def test_cache_dir_created_if_missing(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "baseline_cache"
        assert not nested.exists()
        _BaselineCache(nested)
        assert nested.exists()


class TestB5BaselineCacheHarnessIntegration:
    """End-to-end: with ``baseline_cache_dir`` set, the second run for the same
    (workflow, prompt, model) triple should NOT hit ComfyUI for the baseline."""

    @pytest.fixture()
    def cfg(self, tmp_path: Path) -> HarnessConfig:
        return HarnessConfig(
            api_key="sk-ant-test",
            server_address="127.0.0.1:9999",
            max_iterations=1,
            sync_port=0,
            evolve_from_best=True,
            baseline_first=True,
            baseline_cache_dir=str(tmp_path / "bcache"),
            # Low threshold so the baseline alone meets success and we skip
            # the evolution loop entirely — makes the test deterministic.
            success_threshold=0.5,
        )

    def test_first_run_generates_and_stores(
        self, minimal_workflow: dict, cfg: HarnessConfig
    ) -> None:
        image = b"PNG" + b"\x00" * 80
        mock_client = MagicMock()
        mock_client.queue_prompt.return_value = {"prompt_id": "pid-b"}
        mock_client.wait_for_completion.return_value = {
            "outputs": {"7": {"images": [{"filename": "t.png", "subfolder": "", "type": "output"}]}}
        }
        mock_client.collect_images.return_value = [image]

        h = _make_harness(minimal_workflow, cfg, client=mock_client)
        result = h.run("same prompt")

        assert result == image
        assert mock_client.queue_prompt.call_count == 1  # the baseline gen
        # Cache should now have the entry.
        cache_dir = Path(cfg.baseline_cache_dir)
        assert len(list(cache_dir.glob("*.webp"))) == 1
        assert len(list(cache_dir.glob("*.json"))) == 1

    def test_second_run_hits_cache_and_skips_comfyui(
        self, minimal_workflow: dict, cfg: HarnessConfig
    ) -> None:
        image = b"PNG" + b"\x00" * 80

        # First run populates the cache.
        mock_client_1 = MagicMock()
        mock_client_1.queue_prompt.return_value = {"prompt_id": "pid-first"}
        mock_client_1.wait_for_completion.return_value = {
            "outputs": {"7": {"images": [{"filename": "t.png", "subfolder": "", "type": "output"}]}}
        }
        mock_client_1.collect_images.return_value = [image]
        h1 = _make_harness(minimal_workflow, cfg, client=mock_client_1)
        h1.run("same prompt")

        # Second run MUST hit the cache — make ComfyUI explode if called.
        mock_client_2 = MagicMock()
        mock_client_2.queue_prompt.side_effect = AssertionError(
            "baseline cache MISS: ComfyUI should not be called on second run"
        )
        h2 = _make_harness(minimal_workflow, cfg, client=mock_client_2)
        result = h2.run("same prompt")

        assert result == image
        assert mock_client_2.queue_prompt.call_count == 0

    def test_cache_miss_on_different_prompt(
        self, minimal_workflow: dict, cfg: HarnessConfig
    ) -> None:
        image = b"PNG" + b"\x00" * 80
        mock_client_1 = MagicMock()
        mock_client_1.queue_prompt.return_value = {"prompt_id": "pid-a"}
        mock_client_1.wait_for_completion.return_value = {
            "outputs": {"7": {"images": [{"filename": "t.png", "subfolder": "", "type": "output"}]}}
        }
        mock_client_1.collect_images.return_value = [image]
        h1 = _make_harness(minimal_workflow, cfg, client=mock_client_1)
        h1.run("prompt one")

        # Different prompt → different hash → new submit.
        mock_client_2 = MagicMock()
        mock_client_2.queue_prompt.return_value = {"prompt_id": "pid-b"}
        mock_client_2.wait_for_completion.return_value = {
            "outputs": {"7": {"images": [{"filename": "t.png", "subfolder": "", "type": "output"}]}}
        }
        mock_client_2.collect_images.return_value = [image]
        h2 = _make_harness(minimal_workflow, cfg, client=mock_client_2)
        h2.run("prompt two")
        assert mock_client_2.queue_prompt.call_count == 1

    def test_no_cache_dir_preserves_legacy_behaviour(
        self, minimal_workflow: dict, cfg: HarnessConfig
    ) -> None:
        """When baseline_cache_dir is None the old code path runs unchanged."""
        cfg.baseline_cache_dir = None
        image = b"PNG" + b"\x00" * 80
        mock_client = MagicMock()
        mock_client.queue_prompt.return_value = {"prompt_id": "pid-c"}
        mock_client.wait_for_completion.return_value = {
            "outputs": {"7": {"images": [{"filename": "t.png", "subfolder": "", "type": "output"}]}}
        }
        mock_client.collect_images.return_value = [image]
        h = _make_harness(minimal_workflow, cfg, client=mock_client)
        h.run("prompt once")

        # Baseline gen happened (no cache to consult).
        assert mock_client.queue_prompt.call_count == 1
