"""ComfyUI workflow templates + prompt injection for the GEMS ComfyUI line.

This module is intentionally small: its only job is to produce a valid
ComfyUI API-format workflow dict seeded with the user's prompt, for one
of the supported models (Qwen-Image-2512, Z-Image-Turbo, FLUX.2 [klein]
9B, LongCat-Image).

The base workflow topologies are copied — verbatim — from the reference
workflows used in ``comfyclaw/experiments/geneval2_multimodel.py``.  We
keep them as Python dicts (rather than external JSON files) so the
ComfyUI line has no extra data-file dependencies.
"""

from __future__ import annotations

import copy
import json
from typing import Any

# ---------------------------------------------------------------------------
# Base workflows (API format) — one per supported model
# ---------------------------------------------------------------------------

QWEN_IMAGE_2512_DEFAULT_NEG = (
    "低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，"
    "过度光滑，画面具有AI感，构图混乱，文字模糊，扭曲"
)

LONGCAT_DEFAULT_NEG = (
    "blurry, low resolution, oversaturated, harsh lighting, messy composition, "
    "distorted face, extra fingers, bad anatomy, cheap jewelry, plastic texture, "
    "cartoon, illustration, anime, watermark, text, logo"
)


def _qwen_image_2512_workflow() -> dict:
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "qwen_image_2512_fp8_e4m3fn.safetensors",
                "weight_dtype": "default",
            },
            "_meta": {"title": "UNET Loader (Qwen-Image-2512)"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
                "type": "qwen_image",
                "device": "default",
            },
            "_meta": {"title": "CLIP Loader (Qwen2.5-VL-7B)"},
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "qwen_image_vae.safetensors"},
            "_meta": {"title": "VAE Loader"},
        },
        "5": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["1", 0], "shift": 3.1},
            "_meta": {"title": "Model Sampling AuraFlow"},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 0], "text": ""},
            "_meta": {"title": "Positive Prompt"},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 0], "text": QWEN_IMAGE_2512_DEFAULT_NEG},
            "_meta": {"title": "Negative Prompt"},
        },
        "8": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": 1328, "height": 1328, "batch_size": 1},
            "_meta": {"title": "Empty Latent (1328x1328)"},
        },
        "9": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["5", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["8", 0],
                "seed": 42,
                "steps": 50,
                "cfg": 4.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
            },
            "_meta": {"title": "KSampler"},
        },
        "10": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["9", 0], "vae": ["3", 0]},
            "_meta": {"title": "VAE Decode"},
        },
        "11": {
            "class_type": "SaveImage",
            "inputs": {"images": ["10", 0], "filename_prefix": "GEMS_Qwen"},
            "_meta": {"title": "Save Image"},
        },
    }


def _z_image_turbo_workflow() -> dict:
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "z_image_turbo_bf16.safetensors",
                "weight_dtype": "default",
            },
            "_meta": {"title": "UNET Loader (Z-Image-Turbo)"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen_3_4b.safetensors",
                "type": "lumina2",
                "device": "default",
            },
            "_meta": {"title": "CLIP Loader (Qwen3-4B)"},
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ae.safetensors"},
            "_meta": {"title": "VAE Loader"},
        },
        "5": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["1", 0], "shift": 3},
            "_meta": {"title": "ModelSamplingAuraFlow"},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 0], "text": ""},
            "_meta": {"title": "Positive Prompt"},
        },
        "7": {
            "class_type": "ConditioningZeroOut",
            "inputs": {"conditioning": ["6", 0]},
            "_meta": {"title": "Negative (Zero-Out)"},
        },
        "8": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
            "_meta": {"title": "Empty Latent (1024x1024)"},
        },
        "9": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["5", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["8", 0],
                "seed": 42,
                "steps": 8,
                "cfg": 1,
                "sampler_name": "res_multistep",
                "scheduler": "simple",
                "denoise": 1.0,
            },
            "_meta": {"title": "KSampler"},
        },
        "10": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["9", 0], "vae": ["3", 0]},
            "_meta": {"title": "VAE Decode"},
        },
        "11": {
            "class_type": "SaveImage",
            "inputs": {"images": ["10", 0], "filename_prefix": "GEMS_ZImage"},
            "_meta": {"title": "Save Image"},
        },
    }


def _longcat_image_workflow() -> dict:
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "longcat_image_bf16.safetensors",
                "weight_dtype": "default",
            },
            "_meta": {"title": "UNET Loader (LongCat-Image)"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen_2.5_vl_7b.safetensors",
                "type": "longcat_image",
                "device": "default",
            },
            "_meta": {"title": "CLIP Loader (Qwen2.5-VL-7B)"},
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ae.safetensors"},
            "_meta": {"title": "VAE Loader"},
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 0], "text": ""},
            "_meta": {"title": "Positive Prompt"},
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 0], "text": LONGCAT_DEFAULT_NEG},
            "_meta": {"title": "Negative Prompt"},
        },
        "6": {
            "class_type": "FluxGuidance",
            "inputs": {"conditioning": ["4", 0], "guidance": 4},
            "_meta": {"title": "FluxGuidance (Positive)"},
        },
        "7": {
            "class_type": "FluxGuidance",
            "inputs": {"conditioning": ["5", 0], "guidance": 4},
            "_meta": {"title": "FluxGuidance (Negative)"},
        },
        "8": {
            "class_type": "CFGNorm",
            "inputs": {"model": ["1", 0], "strength": 1},
            "_meta": {"title": "CFGNorm"},
        },
        "9": {
            "class_type": "EmptySD3LatentImage",
            "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
            "_meta": {"title": "Empty Latent (1024x1024)"},
        },
        "10": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["8", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["9", 0],
                "seed": 42,
                "steps": 20,
                "cfg": 4,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
            },
            "_meta": {"title": "KSampler"},
        },
        "11": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["10", 0], "vae": ["3", 0]},
            "_meta": {"title": "VAE Decode"},
        },
        "12": {
            "class_type": "SaveImage",
            "inputs": {"images": ["11", 0], "filename_prefix": "GEMS_LongCat"},
            "_meta": {"title": "Save Image"},
        },
    }


def _flux_klein_9b_workflow() -> dict:
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "flux-2-klein-9b.safetensors",
                "weight_dtype": "default",
            },
            "_meta": {"title": "UNET Loader (FLUX.2 Klein 9B)"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen_3_8b_fp8mixed.safetensors",
                "type": "flux2",
                "device": "default",
            },
            "_meta": {"title": "CLIP Loader (Qwen3-8B)"},
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "flux2-vae.safetensors"},
            "_meta": {"title": "VAE Loader"},
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 0], "text": ""},
            "_meta": {"title": "Positive Prompt"},
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 0], "text": ""},
            "_meta": {"title": "Negative Prompt (empty)"},
        },
        "6": {
            "class_type": "ConditioningZeroOut",
            "inputs": {"conditioning": ["5", 0]},
            "_meta": {"title": "ConditioningZeroOut"},
        },
        "7": {
            "class_type": "CFGGuider",
            "inputs": {
                "model": ["1", 0],
                "positive": ["4", 0],
                "negative": ["6", 0],
                "cfg": 1,
            },
            "_meta": {"title": "CFGGuider"},
        },
        "8": {
            "class_type": "Flux2Scheduler",
            "inputs": {"steps": 4, "width": 1024, "height": 1024},
            "_meta": {"title": "Flux2Scheduler"},
        },
        "9": {
            "class_type": "EmptyFlux2LatentImage",
            "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
            "_meta": {"title": "Empty Flux2 Latent (1024x1024)"},
        },
        "10": {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": 42},
            "_meta": {"title": "RandomNoise"},
        },
        "11": {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": "euler"},
            "_meta": {"title": "KSamplerSelect"},
        },
        "12": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["10", 0],
                "guider": ["7", 0],
                "sampler": ["11", 0],
                "sigmas": ["8", 0],
                "latent_image": ["9", 0],
            },
            "_meta": {"title": "SamplerCustomAdvanced"},
        },
        "13": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["12", 0], "vae": ["3", 0]},
            "_meta": {"title": "VAE Decode"},
        },
        "14": {
            "class_type": "SaveImage",
            "inputs": {"images": ["13", 0], "filename_prefix": "GEMS_FluxKlein"},
            "_meta": {"title": "Save Image"},
        },
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


MODEL_REGISTRY: dict[str, dict[str, Any]] = {
    "qwen-image-2512": {
        "display_name": "Qwen-Image-2512 (20B MMDiT, FP8)",
        "factory": _qwen_image_2512_workflow,
        "skill_id": "qwen-image-2512",
    },
    "z-image-turbo": {
        "display_name": "Z-Image-Turbo (6B S3-DiT, BF16)",
        "factory": _z_image_turbo_workflow,
        "skill_id": "z-image-turbo",
    },
    "longcat-image": {
        "display_name": "LongCat-Image (6B DiT, BF16)",
        "factory": _longcat_image_workflow,
        "skill_id": "longcat-image",
    },
    "flux-klein-9b": {
        "display_name": "FLUX.2 [klein] 9B (BF16)",
        "factory": _flux_klein_9b_workflow,
        "skill_id": "flux-klein-9b",
    },
}

# Aliases so callers can use a friendlier name.
MODEL_ALIASES: dict[str, str] = {
    "qwen": "qwen-image-2512",
    "qwen-image": "qwen-image-2512",
    "qwen_image": "qwen-image-2512",
    "qwen_image_2512": "qwen-image-2512",
    "z-image": "z-image-turbo",
    "z_image": "z-image-turbo",
    "z_image_turbo": "z-image-turbo",
    "zimage": "z-image-turbo",
    "longcat": "longcat-image",
    "longcat_image": "longcat-image",
    "flux": "flux-klein-9b",
    "flux-klein": "flux-klein-9b",
    "flux2-klein": "flux-klein-9b",
    "flux_klein_9b": "flux-klein-9b",
}


def available_models() -> list[str]:
    return list(MODEL_REGISTRY.keys())


def resolve_model(name: str) -> str:
    key = name.strip().lower()
    if key in MODEL_REGISTRY:
        return key
    if key in MODEL_ALIASES:
        return MODEL_ALIASES[key]
    raise ValueError(
        f"Unknown ComfyUI model {name!r}. "
        f"Available: {sorted(MODEL_REGISTRY.keys())}"
    )


def build_base_workflow(model_name: str) -> dict:
    """Return a fresh base-workflow dict for *model_name* (deep-copied)."""
    resolved = resolve_model(model_name)
    return copy.deepcopy(MODEL_REGISTRY[resolved]["factory"]())


def model_skill_id(model_name: str) -> str | None:
    """Return the SKILL_ID in ``agent/skills`` matching this model, if any."""
    resolved = resolve_model(model_name)
    return MODEL_REGISTRY[resolved].get("skill_id")


# ---------------------------------------------------------------------------
# Prompt injection  (mirrors comfyclaw.workflow.WorkflowManager.inject_prompt)
# ---------------------------------------------------------------------------


_SAMPLER_CLASSES = frozenset(
    {
        "KSampler",
        "KSamplerAdvanced",
        "SamplerCustom",
        "SamplerCustomAdvanced",
    }
)

_TEXT_ENCODER_CLASSES = frozenset(
    {
        "CLIPTextEncode",
        "CLIPTextEncodeSDXL",
        "CLIPTextEncodeSD3",
        "CLIPTextEncodeHunyuan",
        "T5TextEncode",
        "FLUXTextEncode",
    }
)

_GUIDER_CLASSES = frozenset({"CFGGuider", "BasicGuider", "DualCFGGuider"})


def _is_link(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], (str, int))
        and isinstance(value[1], int)
    )


def _resolve_text_encoder(
    workflow: dict, start_id: str, max_depth: int = 5
) -> str | None:
    """Follow links from *start_id* to find an enclosing text-encoder node."""
    visited: set[str] = set()
    frontier = [start_id]
    for _ in range(max_depth):
        nxt: list[str] = []
        for nid in frontier:
            if nid in visited:
                continue
            visited.add(nid)
            node = workflow.get(nid)
            if node is None:
                continue
            if node.get("class_type", "") in _TEXT_ENCODER_CLASSES:
                return nid
            for v in node.get("inputs", {}).values():
                if _is_link(v):
                    nxt.append(str(v[0]))
        frontier = nxt
    return None


def _set_encoder_text(workflow: dict, encoder_id: str, value: str) -> bool:
    enc = workflow.get(encoder_id)
    if enc is None:
        return False
    inputs = enc.setdefault("inputs", {})
    if "text_g" in inputs or "text_l" in inputs:
        inputs["text_g"] = value
        inputs["text_l"] = value
    else:
        inputs["text"] = value
    return True


def inject_prompt(
    workflow: dict,
    positive: str | None = None,
    negative: str | None = None,
) -> tuple[list[str], list[str]]:
    """Seed ``positive`` (and optionally ``negative``) into the workflow.

    Walks every sampler / guider node, follows the ``positive``/``negative``
    link to the enclosing ``CLIPTextEncode`` node, and writes the text
    there.  Returns the list of encoder node IDs that were touched.
    """
    pos_ids: list[str] = []
    neg_ids: list[str] = []

    def apply(
        start_link: Any, text_value: str | None, out_list: list[str]
    ) -> None:
        if text_value is None or not _is_link(start_link):
            return
        enc_id = _resolve_text_encoder(workflow, str(start_link[0]))
        if enc_id and _set_encoder_text(workflow, enc_id, text_value):
            if enc_id not in out_list:
                out_list.append(enc_id)

    for node in workflow.values():
        ct = node.get("class_type", "")
        inputs = node.get("inputs", {})

        if ct in _SAMPLER_CLASSES:
            apply(inputs.get("positive"), positive, pos_ids)
            apply(inputs.get("negative"), negative, neg_ids)

            guider_link = inputs.get("guider")
            if _is_link(guider_link):
                gid = str(guider_link[0])
                guider = workflow.get(gid)
                if guider and guider.get("class_type", "") in _GUIDER_CLASSES:
                    ginputs = guider.get("inputs", {})
                    apply(ginputs.get("positive"), positive, pos_ids)
                    apply(ginputs.get("negative"), negative, neg_ids)

        elif ct in _GUIDER_CLASSES:
            apply(inputs.get("positive"), positive, pos_ids)
            apply(inputs.get("negative"), negative, neg_ids)

    return pos_ids, neg_ids


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def build_workflow_for_prompt(
    model_name: str,
    positive_prompt: str,
    negative_prompt: str | None = None,
    seed: int | None = None,
) -> dict:
    """One-shot helper: base workflow → prompt injected → ready to submit."""
    wf = build_base_workflow(model_name)
    inject_prompt(wf, positive=positive_prompt, negative=negative_prompt)
    if seed is not None:
        for node in wf.values():
            if node.get("class_type") in ("KSampler", "KSamplerAdvanced"):
                node.setdefault("inputs", {})["seed"] = int(seed)
            if node.get("class_type") == "RandomNoise":
                node.setdefault("inputs", {})["noise_seed"] = int(seed)
    return wf


def dump_workflow(workflow: dict, indent: int = 2) -> str:
    """Pretty-print a workflow as JSON (useful for logging / debugging)."""
    return json.dumps(workflow, indent=indent, ensure_ascii=False)
