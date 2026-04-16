"""ComfyUI-line variant of GEMS.

This is the *second line* of GEMS: instead of calling a dedicated HTTP
generation server (``qwen_image.py`` / ``z_image.py``), each ``generate``
call produces a complete ComfyUI API-format workflow for the chosen
model, submits it to a running ComfyUI server, and returns the first
output image's bytes.

Everything else — prompt decomposition, VLM verification, experience
summarisation, iterative refinement, skill routing — is inherited
unchanged from :class:`agent.GEMS.GEMS`.

Supported models (selected via the ``model`` constructor argument):

* ``qwen-image-2512``    — Qwen-Image-2512 (20B MMDiT, FP8)
* ``z-image-turbo``      — Z-Image-Turbo (6B S3-DiT, BF16)
* ``flux-klein-9b``      — FLUX.2 [klein] 9B (BF16)
* ``longcat-image``      — LongCat-Image (6B DiT, BF16)

Each model has a corresponding SKILL.md under ``agent/skills/<model>``
imported from comfyclaw so the planner can route to it automatically.
"""

from __future__ import annotations

import json
import os
from typing import Any

from agent.GEMS import GEMS
from agent.comfy_client import ComfyClient
from agent.comfy_workflow import (
    MODEL_REGISTRY,
    available_models,
    build_workflow_for_prompt,
    dump_workflow,
    model_skill_id,
    resolve_model,
)


class ComfyGEMS(GEMS):
    """GEMS variant that generates images via a ComfyUI workflow.

    Parameters
    ----------
    model :
        One of ``qwen-image-2512``, ``z-image-turbo``, ``flux-klein-9b``,
        ``longcat-image`` (aliases accepted, see ``comfy_workflow.py``).
    comfyui_server :
        ``host:port`` (or ``http://host:port``) of a running ComfyUI
        instance.  Defaults to ``127.0.0.1:8188``.
    max_iterations :
        Same as :class:`GEMS` — decompose→verify→refine iteration cap.
    mllm_url :
        Optional override passed through to :class:`GEMS`.
    default_negative :
        If set, used as the negative prompt for every generation.  Leave
        ``None`` to use each workflow's built-in default.
    workflow_timeout :
        Seconds to wait for a single ComfyUI job to finish.
    workflow_log_dir :
        If set, every submitted workflow is dumped as JSON here for
        inspection / reuse.  ``None`` disables logging.
    seed :
        If set, pin the KSampler seed to this value (reproducibility).
    """

    def __init__(
        self,
        model: str = "qwen-image-2512",
        comfyui_server: str = "127.0.0.1:8188",
        max_iterations: int = 5,
        mllm_url: str | None = None,
        default_negative: str | None = None,
        workflow_timeout: int = 600,
        workflow_log_dir: str | None = None,
        seed: int | None = None,
    ) -> None:
        # ``GEMS`` / ``BaseAgent`` require a gen_url; we reuse the ComfyUI
        # server address as a human-readable identifier.  The base
        # ``generate`` method is overridden below so the URL is never
        # actually POSTed to.
        super().__init__(
            gen_url=f"comfyui://{comfyui_server}",
            mllm_url=mllm_url,
            max_iterations=max_iterations,
        )
        # NOTE: BaseAgent already set ``self.model`` to the LiteLLM model
        # (e.g. ``anthropic/claude-sonnet-4-6``).  The image model is
        # kept under a separate attribute so ``think()`` continues to
        # dispatch to the correct MLLM.
        self.image_model = resolve_model(model)
        self.model_display_name = MODEL_REGISTRY[self.image_model]["display_name"]
        self.comfyui_server = comfyui_server
        self.default_negative = default_negative
        self.workflow_timeout = workflow_timeout
        self.workflow_log_dir = workflow_log_dir
        self.seed = seed

        self.comfy = ComfyClient(server_address=comfyui_server)
        self._last_workflow: dict | None = None
        self._workflow_counter = 0

        if workflow_log_dir:
            os.makedirs(workflow_log_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def available_models() -> list[str]:
        return available_models()

    @property
    def last_workflow(self) -> dict | None:
        """The most recently submitted ComfyUI workflow (deep copy)."""
        if self._last_workflow is None:
            return None
        return json.loads(json.dumps(self._last_workflow))

    def build_workflow(
        self,
        prompt: str,
        negative: str | None = None,
    ) -> dict:
        """Build (but do NOT submit) a ComfyUI workflow for *prompt*."""
        neg = negative if negative is not None else self.default_negative
        return build_workflow_for_prompt(
            model_name=self.image_model,
            positive_prompt=prompt,
            negative_prompt=neg,
            seed=self.seed,
        )

    # ------------------------------------------------------------------
    # The only behavioural override: how we actually turn a prompt into
    # image bytes.  Everything in the GEMS decompose/verify/refine loop
    # above calls ``self.generate(prompt)`` and therefore picks this up
    # for free.
    # ------------------------------------------------------------------

    def generate(self, prompt: str) -> bytes:
        workflow = self.build_workflow(prompt)
        self._last_workflow = workflow
        self._dump_workflow_if_requested(workflow, prompt)
        return self.comfy.run_workflow(
            workflow,
            timeout=self.workflow_timeout,
        )

    # ------------------------------------------------------------------
    # Skill routing helper — if the user hasn't written a SKILL.md match,
    # we fall back to the skill bundled for the selected model.  This
    # ensures the planner's prompt-enhancement step receives the model's
    # recipe (sampler settings, negative prompt advice, etc.) even when
    # the original user prompt doesn't explicitly trigger a skill.
    # ------------------------------------------------------------------

    def plan(self, original_prompt: str) -> str:
        refined = super().plan(original_prompt)
        if refined != original_prompt:
            return refined

        sid = model_skill_id(self.image_model)
        if sid and sid in self.skill_manager.skills:
            print(
                f"🎯 Falling back to model-specific skill for {self.image_model}: {sid}"
            )
            skill_info = self.skill_manager.skills[sid]
            refine_task = (
                "Based on the following skill instructions, enhance the user's prompt.\n"
                f"### Skill Instructions:\n{skill_info['instructions']}\n\n"
                f"### Original Prompt: {original_prompt}\n\n"
                "Return ONLY the final enhanced prompt text."
            )
            try:
                enhanced = self.think(refine_task).strip()
                if enhanced:
                    print(f"🚀 Enhanced Prompt: {enhanced}")
                    return enhanced
            except Exception as exc:
                print(f"[ComfyGEMS] skill fallback failed: {exc}")
        return original_prompt

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _dump_workflow_if_requested(self, workflow: dict, prompt: str) -> None:
        if not self.workflow_log_dir:
            return
        self._workflow_counter += 1
        fname = f"workflow_{self._workflow_counter:03d}.json"
        fpath = os.path.join(self.workflow_log_dir, fname)
        payload: dict[str, Any] = {
            "model": self.image_model,
            "model_display_name": self.model_display_name,
            "prompt": prompt,
            "workflow": workflow,
        }
        with open(fpath, "w", encoding="utf-8") as fh:
            fh.write(dump_workflow(payload))
        print(f"[ComfyGEMS] 🧾 Workflow logged → {fpath}")
