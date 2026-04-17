"""Agentic ComfyUI-line variant of GEMS (tool-use workflow construction).

This is the **third line** of GEMS.  Unlike :class:`agent.comfy_gems.ComfyGEMS`
(which fills in a hard-coded ComfyUI workflow template chosen by model name),
``ComfyGEMSAgentic`` treats workflow construction as a *planning problem*:

    LLM decides  ──[ tool call: add_node, connect, set_param, ... ]──▶
    WorkflowManager (in-memory ComfyUI graph) ──submit──▶ ComfyUI ──▶ image

Every generation is produced by running a tool-use loop against the chosen
MLLM (Claude / GPT-4o / Gemini / Ollama — anything LiteLLM supports) until
the model calls ``finalize_workflow``.  Then the resulting graph is posted
to a live ComfyUI server and the first output image is returned.

Key properties
--------------

* **No hard-coded templates.**  The LLM builds the graph node-by-node,
  starting from an empty ``WorkflowManager`` (or an optional seed template
  for faster convergence).
* **Same GEMS pipeline.**  ``run_with_trace`` / ``plan`` / ``decompose`` /
  ``verify_image`` / refinement — all inherited verbatim from
  :class:`~agent.GEMS.GEMS`.  The *only* behavioural override is
  :meth:`ComfyGEMSAgentic.generate`.
* **Within-task evolution, across-task isolation.**  Inside one
  ``run_with_trace`` call, the workflow *persists* across GEMS iterations,
  so later rounds make incremental edits (swap sampler, add hires-fix,
  tweak CFG, rewrite prompt) on top of the graph already built in round 1
  — much cheaper than rebuilding from scratch every round.  Between tasks,
  the graph is wiped automatically so one user prompt never leaks its
  workflow into the next.
* **Reuses proven plumbing.**  Graph mutations go through
  ``comfyclaw.workflow.WorkflowManager`` (battle-tested under the ``comfyclaw``
  harness); network I/O goes through :class:`agent.comfy_client.ComfyClient`;
  skill routing / VLM verify / experience refinement are inherited from
  :class:`agent.GEMS.GEMS`.

Example
-------

.. code-block:: python

    from agent.comfy_gems_agentic import ComfyGEMSAgentic

    agent = ComfyGEMSAgentic(
        comfyui_server="127.0.0.1:8188",
        seed_model="qwen-image-2512",    # or None to build from an empty graph
        max_tool_rounds=30,
    )
    # Same entrypoint as GEMS / ComfyGEMS:
    result = agent.run_with_trace({"prompt": "a red fox at dawn, photorealistic"})
    # → {"best_image": bytes, "all_images": [...], "trace": {...}}
"""

from __future__ import annotations

import copy
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any

import litellm

from agent.GEMS import GEMS
from agent.comfy_client import ComfyClient
from agent.comfy_workflow import (
    available_models,
    build_base_workflow,
    model_skill_id,
    resolve_model,
)


# ---------------------------------------------------------------------------
# WorkflowManager import (from comfyclaw — adds path if not pip-installed)
# ---------------------------------------------------------------------------

def _import_workflow_manager():
    try:
        from comfyclaw.workflow import WorkflowManager
        return WorkflowManager
    except ImportError:
        pass
    # Fallback: sibling checkout under /workspace/comfyclaw
    for candidate in (
        os.path.join(os.path.dirname(__file__), "..", "..", "comfyclaw"),
        "/workspace/comfyclaw",
    ):
        candidate = os.path.abspath(candidate)
        if os.path.isdir(os.path.join(candidate, "comfyclaw")):
            if candidate not in sys.path:
                sys.path.insert(0, candidate)
            from comfyclaw.workflow import WorkflowManager  # type: ignore
            return WorkflowManager
    raise ImportError(
        "ComfyGEMSAgentic needs comfyclaw.workflow.WorkflowManager. "
        "Install comfyclaw (pip install -e /path/to/comfyclaw) or place a "
        "comfyclaw checkout next to the GEMS repo."
    )


WorkflowManager = _import_workflow_manager()


# ---------------------------------------------------------------------------
# System prompt (concise — ClawAgent's is 150+ lines; we keep only the parts
# relevant for GEMS's decompose/verify/refine use-case)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a ComfyUI workflow engineer.  You BUILD a complete ComfyUI API-format
graph by calling the provided tools, then hand it off with `finalize_workflow`.

Iteration protocol
------------------
1. `inspect_workflow`  — always start by seeing what exists.
2. If the workflow is EMPTY, build a full text-to-image pipeline:
     (a) `query_available_models` for each loader type you plan to use
         (`checkpoints`, `unets`, `vae`, etc.) — NEVER guess filenames.
     (b) Add nodes via `add_node`, wire them via `connect_nodes`, set
         parameters via `set_param`.  A minimal text-to-image graph looks
         like:
           UNETLoader / CheckpointLoader  ──▶ (ModelSamplingAuraFlow) ──▶ KSampler
           CLIPLoader / (inside checkpoint) ──▶ CLIPTextEncode (pos) ─▶ KSampler.positive
                                                 CLIPTextEncode (neg) ─▶ KSampler.negative
           EmptySD3LatentImage / EmptyLatentImage ──▶ KSampler.latent_image
           VAELoader / (inside checkpoint) ──▶ VAEDecode ──▶ SaveImage
     (c) `set_prompt` injects the positive + negative text across every
         sampler→encoder link in one shot — use it instead of manually
         setting `text` on each encoder.
3. If the workflow already has nodes, EVOLVE it based on the user's request
   and the `Verifier Feedback` section (if any).  Typical edits:
     - update positive/negative prompt via `set_prompt`
     - tweak sampler params (steps, cfg, sampler_name) via `set_param`
     - swap the seed, change dimensions on the latent node
     - add hires-fix: LatentUpscaleBy → second KSampler → VAEDecode → SaveImage
4. `validate_workflow` to catch dangling refs / missing outputs.
5. `finalize_workflow` when the graph is complete.  Validation runs again;
   `finalize_workflow` will be rejected if there are outstanding errors.

Link format
-----------
In ComfyUI API format, node inputs that are "wires" use the form
``[src_node_id_str, output_slot_int]``.  When you call `add_node` with
`inputs`, you can pre-wire by setting fields to that list shape, e.g.:

    add_node(class_type="KSampler", inputs={
        "model":    ["3", 0],
        "positive": ["5", 0],
        "negative": ["6", 0],
        "latent_image": ["7", 0],
        "seed": 42, "steps": 20, "cfg": 4.0,
        "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0
    })

Or build the node first with only scalars, then `connect_nodes` the links.

Output slot conventions
-----------------------
    CheckpointLoaderSimple : 0=MODEL, 1=CLIP, 2=VAE
    UNETLoader             : 0=MODEL
    CLIPLoader             : 0=CLIP
    VAELoader              : 0=VAE
    CLIPTextEncode         : 0=CONDITIONING
    KSampler               : 0=LATENT
    VAEDecode              : 0=IMAGE
    EmptySD3/LatentImage   : 0=LATENT

A workflow MUST terminate in a `SaveImage` node, with
`filename_prefix` set (any short string).
"""


# ---------------------------------------------------------------------------
# Tool schemas (OpenAI / LiteLLM function-calling format)
# ---------------------------------------------------------------------------

def _tool(name: str, desc: str, params: dict) -> dict:
    return {
        "type": "function",
        "function": {"name": name, "description": desc, "parameters": params},
    }


_TOOLS: list[dict] = [
    _tool(
        "inspect_workflow",
        "Return a compact human-readable summary of every node, its ID, "
        "class_type, title, and inputs (scalars + link refs).",
        {"type": "object", "properties": {}, "required": []},
    ),
    _tool(
        "query_available_models",
        "Ask the live ComfyUI server which model files are installed for a given "
        "loader type. Call this BEFORE choosing a filename for any loader node.",
        {
            "type": "object",
            "properties": {
                "model_type": {
                    "type": "string",
                    "description": "One of: checkpoints | unets | vae | loras | "
                                   "controlnets | upscale_models | clip | clip_vision",
                },
            },
            "required": ["model_type"],
        },
    ),
    _tool(
        "add_node",
        "Append a new node to the workflow. Returns the newly assigned node_id.",
        {
            "type": "object",
            "properties": {
                "class_type": {"type": "string", "description": "ComfyUI class name, e.g. 'KSampler'."},
                "nickname": {"type": "string", "description": "Optional title for the node."},
                "inputs": {
                    "type": "object",
                    "description": "Initial input values. Scalars and link refs "
                                   "(`[src_node_id_str, slot_int]`) both accepted.",
                },
            },
            "required": ["class_type"],
        },
    ),
    _tool(
        "connect_nodes",
        "Wire src_node_id[src_output_index] into dst_node_id.dst_input_name.",
        {
            "type": "object",
            "properties": {
                "src_node_id": {"type": "string"},
                "src_output_index": {"type": "integer"},
                "dst_node_id": {"type": "string"},
                "dst_input_name": {"type": "string"},
            },
            "required": ["src_node_id", "src_output_index", "dst_node_id", "dst_input_name"],
        },
    ),
    _tool(
        "set_param",
        "Set a scalar input on an existing node (e.g. steps, cfg, text, filename_prefix).",
        {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "param_name": {"type": "string"},
                "value": {},
            },
            "required": ["node_id", "param_name", "value"],
        },
    ),
    _tool(
        "delete_node",
        "Remove a node and clean up dangling references to it in other nodes.",
        {
            "type": "object",
            "properties": {"node_id": {"type": "string"}},
            "required": ["node_id"],
        },
    ),
    _tool(
        "set_prompt",
        "Inject positive (and optionally negative) text across every sampler → "
        "encoder link. Use this to set prompts without having to look up node IDs.",
        {
            "type": "object",
            "properties": {
                "positive_text": {"type": "string"},
                "negative_text": {"type": "string"},
            },
            "required": [],
        },
    ),
    _tool(
        "validate_workflow",
        "Check the graph for dangling link references, missing outputs, etc. "
        "Returns a list of issues (empty = valid).",
        {"type": "object", "properties": {}, "required": []},
    ),
    _tool(
        "finalize_workflow",
        "Signal the graph is complete and ready to submit. Auto-validates first; "
        "rejected if there are outstanding errors.",
        {
            "type": "object",
            "properties": {"rationale": {"type": "string"}},
            "required": ["rationale"],
        },
    ),
]


# ---------------------------------------------------------------------------
# The agent
# ---------------------------------------------------------------------------


class ComfyGEMSAgentic(GEMS):
    """GEMS variant whose ``generate()`` uses LLM tool-use to BUILD the
    ComfyUI workflow node-by-node.

    Parameters
    ----------
    comfyui_server :
        ``host:port`` of a running ComfyUI server.
    seed_model :
        If set (e.g. ``"qwen-image-2512"``, ``"z-image-turbo"``), the
        workflow is pre-seeded with that static template and the LLM only
        edits it — much faster than building from scratch but less agentic.
        Leave ``None`` to force the LLM to build from an empty graph.
    fresh_each_round :
        If ``True``, the workflow is reset to the seed (or empty) on every
        :meth:`generate` call.  Default ``False`` — the graph persists across
        GEMS iterations so round-2 edits are *structural*, not just prompt
        rewrites.
    max_tool_rounds :
        Safety cap on tool calls per ``generate()`` invocation.
    builder_model :
        LiteLLM model string used for the tool-use loop (e.g.
        ``"anthropic/claude-sonnet-4-5"``).  Defaults to ``self.model`` —
        whatever ``LITELLM_MODEL`` resolves to at construction time.
    max_iterations :
        GEMS decompose/verify/refine cap, same as parent.
    workflow_log_dir :
        If set, every submitted workflow is dumped as JSON here for inspection.
    workflow_timeout :
        Seconds to wait for each ComfyUI job.
    seed :
        Pin KSampler / RandomNoise seeds for reproducibility (overrides
        whatever the LLM wrote).
    """

    def __init__(
        self,
        comfyui_server: str = "127.0.0.1:8188",
        seed_model: str | None = None,
        fresh_each_round: bool = False,
        max_tool_rounds: int = 30,
        builder_model: str | None = None,
        max_iterations: int = 5,
        mllm_url: str | None = None,
        workflow_log_dir: str | None = None,
        workflow_timeout: int = 600,
        seed: int | None = None,
        inject_skill_into_builder: bool = True,
        skill_max_chars: int = 12000,
        skill_model: str | None = None,
    ) -> None:
        super().__init__(
            gen_url=f"comfyui-agentic://{comfyui_server}",
            mllm_url=mllm_url,
            max_iterations=max_iterations,
        )
        if seed_model is not None:
            seed_model = resolve_model(seed_model)
        if skill_model is not None:
            skill_model = resolve_model(skill_model)
        self.comfyui_server = comfyui_server
        self.seed_model = seed_model
        # ``skill_model`` lets you inject a model recipe even when seed_model
        # is None (i.e. build-from-empty-graph).  Defaults to seed_model.
        self.skill_model = skill_model or seed_model
        self.fresh_each_round = fresh_each_round
        self.max_tool_rounds = max_tool_rounds
        self.builder_model = builder_model or self.model
        self.workflow_log_dir = workflow_log_dir
        self.workflow_timeout = workflow_timeout
        self.seed = seed
        self.inject_skill_into_builder = inject_skill_into_builder
        self.skill_max_chars = skill_max_chars

        self.comfy = ComfyClient(server_address=comfyui_server)
        self._wm: WorkflowManager | None = None
        self._workflow_counter = 0
        self._generate_call_count = 0
        self._last_finalize_rationale: str | None = None
        self._last_tool_trace: list[dict] = []

        if workflow_log_dir:
            os.makedirs(workflow_log_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @staticmethod
    def available_seed_models() -> list[str]:
        return available_models()

    @property
    def last_workflow(self) -> dict | None:
        return None if self._wm is None else copy.deepcopy(self._wm.workflow)

    @property
    def last_tool_trace(self) -> list[dict]:
        return list(self._last_tool_trace)

    # ------------------------------------------------------------------
    # Workflow lifecycle helpers
    # ------------------------------------------------------------------

    def reset_workflow(self) -> None:
        """Drop the current graph.  Next ``generate()`` rebuilds from seed."""
        self._wm = None
        self._generate_call_count = 0
        self._last_finalize_rationale = None
        self._last_tool_trace = []

    # ------------------------------------------------------------------
    # Task-level reset: align graph lifecycle with ONE user task.
    # Within a task, `generate()` is called multiple times by the GEMS
    # decompose/verify/refine loop and the graph *evolves* across rounds
    # (efficient — later rounds only diff the previous graph).
    # Between tasks, we wipe the graph so task B never inherits A's state.
    # ------------------------------------------------------------------

    def run_with_trace(self, item: dict) -> dict:
        self.reset_workflow()
        return super().run_with_trace(item)

    def _ensure_workflow_manager(self) -> WorkflowManager:
        if self._wm is None or self.fresh_each_round:
            if self.seed_model:
                base = build_base_workflow(self.seed_model)
                self._wm = WorkflowManager(base)
            else:
                self._wm = WorkflowManager({})
        return self._wm

    def _pin_seed_if_requested(self) -> None:
        if self.seed is None or self._wm is None:
            return
        for node in self._wm.workflow.values():
            ct = node.get("class_type", "")
            inputs = node.setdefault("inputs", {})
            if ct in ("KSampler", "KSamplerAdvanced"):
                inputs["seed"] = int(self.seed)
            elif ct == "RandomNoise":
                inputs["noise_seed"] = int(self.seed)

    # ------------------------------------------------------------------
    # The GEMS contract: generate(prompt) -> image bytes
    # ------------------------------------------------------------------

    def generate(self, prompt: str) -> bytes:
        self._generate_call_count += 1
        wm = self._ensure_workflow_manager()

        # Let the LLM drive the graph via tool-use.
        user_msg = self._build_user_message(prompt)
        self._run_tool_loop(wm, user_msg)

        # Pin seed last so the LLM's value is overridden when requested.
        self._pin_seed_if_requested()

        # One more safety pass to catch any missed wiring.
        WorkflowManager.ensure_output_wiring(wm.workflow)

        workflow = wm.to_dict()
        self._dump_workflow_if_requested(workflow, prompt)
        return self.comfy.run_workflow(
            workflow,
            timeout=self.workflow_timeout,
        )

    # ------------------------------------------------------------------
    # Tool-use driver
    # ------------------------------------------------------------------

    def _seed_model_skill_block(self) -> str | None:
        """Render the SKILL.md of ``self.seed_model`` as a builder-facing recipe.

        Returns ``None`` when skill injection is disabled, the seed model has
        no registered ``skill_id``, or the corresponding SKILL.md is not
        installed under ``agent/skills/``.  The loaded body is truncated to
        ``self.skill_max_chars`` to keep per-round token cost bounded.
        """
        if not self.inject_skill_into_builder or not self.skill_model:
            return None
        try:
            sid = model_skill_id(self.skill_model)
        except ValueError:
            return None
        if not sid:
            return None
        skills = getattr(self.skill_manager, "skills", {}) or {}
        info = skills.get(sid)
        if not info:
            return None
        body = (info.get("instructions") or "").strip()
        if not body:
            return None
        if self.skill_max_chars and len(body) > self.skill_max_chars:
            body = body[: self.skill_max_chars].rstrip() + "\n\n[...truncated...]"
        return (
            f"## Model recipe ({sid})\n"
            "Authoritative ComfyUI recipe for the seed model. It tells you the "
            "correct `class_type`s, CLIPLoader `type`, sampler/scheduler/cfg/"
            "steps, mandatory conditioning nodes (e.g. `ModelSamplingAuraFlow`, "
            "`ConditioningZeroOut`), and model filenames. Follow this recipe "
            "unless the user's prompt explicitly asks to deviate — do NOT "
            "'optimize' these defaults on your own.\n\n"
            f"{body}"
        )

    def _build_user_message(self, prompt: str) -> str:
        parts: list[str] = []
        skill_block = self._seed_model_skill_block()
        if skill_block:
            parts.append(skill_block)
        parts.append(f"## Image goal\n{prompt}")
        parts.append(f"## GEMS iteration\n{self._generate_call_count}")
        wm = self._wm
        if wm is not None:
            if len(wm.workflow) == 0:
                parts.append(
                    "## Current workflow state\n"
                    "EMPTY — no nodes yet. Build a full text-to-image pipeline "
                    "from scratch."
                )
            else:
                parts.append(
                    "## Current workflow state (from previous round — EVOLVE it)\n"
                    + WorkflowManager.summarize(wm.workflow)
                    + "\n\nUpdate prompts via `set_prompt`, tune scalars via "
                    "`set_param`, add structural upgrades (hires-fix, different "
                    "sampler, regional prompting) as warranted."
                )
        parts.append(
            "Start with `inspect_workflow`, then build/evolve the graph, "
            "then `validate_workflow`, then `finalize_workflow`."
        )
        return "\n\n".join(parts)

    def _run_tool_loop(self, wm: WorkflowManager, user_msg: str) -> None:
        messages: list[dict] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]
        self._last_tool_trace = []
        rationale: str | None = None

        for round_i in range(1, self.max_tool_rounds + 1):
            try:
                resp = litellm.completion(
                    model=self.builder_model,
                    max_tokens=4096,
                    tools=_TOOLS,
                    messages=messages,
                )
            except Exception as exc:
                print(f"[ComfyGEMSAgentic] LiteLLM error on round {round_i}: {exc}")
                break

            choice = resp.choices[0]
            msg = choice.message
            messages.append(msg)

            if msg.content:
                print(f"[ComfyGEMSAgentic] 💭 {msg.content[:300]}")

            finish = choice.finish_reason
            if finish in ("stop", "end_turn"):
                print("[ComfyGEMSAgentic] LLM ended turn without finalizing.")
                break
            if finish != "tool_calls" or not getattr(msg, "tool_calls", None):
                print(f"[ComfyGEMSAgentic] Unexpected finish_reason={finish!r}")
                break

            done = False
            for tc in msg.tool_calls:
                tname = tc.function.name
                try:
                    targs = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    targs = {}

                result_text, stop, extra = self._dispatch(tname, targs, wm)
                self._last_tool_trace.append(
                    {"round": round_i, "name": tname, "args": targs, "result": result_text[:400]}
                )
                print(
                    f"[ComfyGEMSAgentic] 🔧 {tname}({_abbrev(targs)}) "
                    f"→ {result_text[:180]}"
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_text,
                    }
                )
                if stop:
                    done = True
                    rationale = extra.get("rationale") if extra else None

            if done:
                break
        else:
            print(
                f"[ComfyGEMSAgentic] ⚠️ Hit max_tool_rounds={self.max_tool_rounds} "
                f"without finalize_workflow — submitting current graph as-is."
            )

        self._last_finalize_rationale = rationale
        if rationale:
            print(f"[ComfyGEMSAgentic] 🎯 Finalize: {rationale[:200]}")

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    def _dispatch(
        self,
        name: str,
        inputs: dict,
        wm: WorkflowManager,
    ) -> tuple[str, bool, dict | None]:
        try:
            if name == "inspect_workflow":
                return WorkflowManager.summarize(wm.workflow), False, None

            if name == "query_available_models":
                return self._query_models(inputs.get("model_type", "")), False, None

            if name == "add_node":
                nid = wm.add_node(
                    inputs["class_type"],
                    inputs.get("nickname"),
                    **(inputs.get("inputs") or {}),
                )
                return f"✅ Added node {nid} ({inputs['class_type']}).", False, None

            if name == "connect_nodes":
                wm.connect(
                    str(inputs["src_node_id"]),
                    int(inputs.get("src_output_index", 0)),
                    str(inputs["dst_node_id"]),
                    inputs["dst_input_name"],
                )
                return (
                    f"✅ {inputs['src_node_id']}[{inputs.get('src_output_index', 0)}]"
                    f" → {inputs['dst_node_id']}.{inputs['dst_input_name']}"
                ), False, None

            if name == "set_param":
                wm.set_param(
                    str(inputs["node_id"]), inputs["param_name"], inputs["value"]
                )
                return (
                    f"✅ {inputs['node_id']}.{inputs['param_name']} = "
                    f"{json.dumps(inputs['value'])[:80]}"
                ), False, None

            if name == "delete_node":
                wm.delete_node(str(inputs["node_id"]))
                return f"✅ Deleted node {inputs['node_id']}", False, None

            if name == "set_prompt":
                pos = (inputs.get("positive_text") or "").strip() or None
                neg = (inputs.get("negative_text") or "").strip() or None
                pos_ids, neg_ids = wm.inject_prompt(positive=pos, negative=neg)
                bits = []
                if pos_ids:
                    bits.append(f"positive → {pos_ids}")
                if neg_ids:
                    bits.append(f"negative → {neg_ids}")
                if not bits:
                    return (
                        "⚠️ set_prompt wrote nothing — no sampler→CLIPTextEncode "
                        "link exists yet. Add a sampler + encoder and wire them first.",
                        False, None,
                    )
                return "✅ " + "; ".join(bits), False, None

            if name == "validate_workflow":
                errs = WorkflowManager.validate_graph(wm.workflow)
                if not errs:
                    return (
                        f"✅ Valid ({len(wm.workflow)} nodes, no issues).",
                        False, None,
                    )
                return (
                    "⚠️ Validation issues:\n  • " + "\n  • ".join(errs)
                    + "\n\nFix before finalizing.",
                    False, None,
                )

            if name == "finalize_workflow":
                errs = WorkflowManager.validate_graph(wm.workflow)
                if errs:
                    return (
                        "⚠️ Cannot finalize — validation still failing:\n  • "
                        + "\n  • ".join(errs),
                        False, None,
                    )
                return (
                    "✅ Workflow finalized.",
                    True,
                    {"rationale": inputs.get("rationale", "")},
                )

            return f"❌ Unknown tool: {name}", False, None

        except KeyError as exc:
            return f"❌ Missing arg for {name}: {exc}", False, None
        except Exception as exc:
            return f"❌ Tool error ({name}): {exc}", False, None

    # ------------------------------------------------------------------
    # ComfyUI /object_info query (copied + trimmed from ClawAgent)
    # ------------------------------------------------------------------

    _MODEL_TYPE_MAP: dict[str, tuple[str, str]] = {
        "loras": ("LoraLoader", "lora_name"),
        "controlnets": ("ControlNetLoader", "control_net_name"),
        "checkpoints": ("CheckpointLoaderSimple", "ckpt_name"),
        "unets": ("UNETLoader", "unet_name"),
        "vae": ("VAELoader", "vae_name"),
        "upscale_models": ("UpscaleModelLoader", "model_name"),
        "clip": ("CLIPLoader", "clip_name"),
        "clip_vision": ("CLIPVisionLoader", "clip_name"),
    }

    def _query_models(self, model_type: str) -> str:
        entry = self._MODEL_TYPE_MAP.get(model_type.lower())
        if not entry:
            return (
                f"❌ Unknown model_type {model_type!r}. Valid: "
                f"{sorted(self._MODEL_TYPE_MAP)}"
            )
        node_class, param = entry
        try:
            url = (
                f"http://{self.comfyui_server}/object_info/"
                f"{urllib.parse.quote(node_class)}"
            )
            with urllib.request.urlopen(url, timeout=8) as r:
                data = json.loads(r.read())
            models = (
                data.get(node_class, {})
                .get("input", {})
                .get("required", {})
                .get(param, [[]])[0]
            )
            if not models:
                return f"No {model_type} found (ComfyUI returned empty list)."
            lines = "\n".join(f"  - {m}" for m in models)
            return f"Available {model_type} ({len(models)}):\n{lines}"
        except Exception as exc:
            return f"❌ Could not query {model_type}: {exc}"

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _dump_workflow_if_requested(self, workflow: dict, prompt: str) -> None:
        if not self.workflow_log_dir:
            return
        self._workflow_counter += 1
        fname = f"workflow_{self._workflow_counter:03d}.json"
        fpath = os.path.join(self.workflow_log_dir, fname)
        payload: dict[str, Any] = {
            "prompt": prompt,
            "iteration": self._generate_call_count,
            "seed_model": self.seed_model,
            "finalize_rationale": self._last_finalize_rationale,
            "tool_trace": self._last_tool_trace,
            "workflow": workflow,
        }
        with open(fpath, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        print(f"[ComfyGEMSAgentic] 🧾 Workflow logged → {fpath}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _abbrev(d: dict, max_len: int = 80) -> str:
    """One-line compact repr of a tool-call argument dict (for logging)."""
    try:
        s = json.dumps(d, ensure_ascii=False)
    except Exception:
        s = str(d)
    return s if len(s) <= max_len else s[: max_len - 1] + "…"
