"""
Explore ComfyUI node ecosystem and classify nodes into pipeline stages.

Queries the ComfyUI ``/object_info`` endpoint, analyses each node's I/O
type signatures, and emits a ``stage_map.json`` that maps pipeline stages
to their relevant node classes and agent tools.

Usage::

    python -m comfyclaw.skills.explore.scripts.explore_nodes \
        --server 127.0.0.1:8188 --output stage_map.json
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

# ── Stage definitions ──────────────────────────────────────────────────────

STAGE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "loading": {
        "description": "Model, CLIP, VAE, and adapter loading",
        "output_types": {"MODEL", "CLIP", "VAE", "CONTROL_NET"},
        "agent_tools": ["query_available_models", "add_node", "set_param", "add_lora_loader"],
    },
    "conditioning": {
        "description": "Prompt encoding and conditioning control",
        "output_types": {"CONDITIONING"},
        "input_types": {"CLIP"},
        "agent_tools": ["set_prompt", "add_regional_attention"],
    },
    "sampling": {
        "description": "Diffusion sampling (denoising latents)",
        "requires_inputs": {"MODEL", "CONDITIONING", "LATENT"},
        "output_types": {"LATENT"},
        "agent_tools": ["add_node", "set_param"],
    },
    "latent_ops": {
        "description": "Latent-space transforms (empty, upscale, composite)",
        "pure_types": {"LATENT"},
        "agent_tools": ["add_node", "set_param", "add_hires_fix"],
    },
    "decoding": {
        "description": "VAE decoding / encoding between latent and pixel space",
        "requires_inputs": {"LATENT", "VAE"},
        "output_types": {"IMAGE"},
        "agent_tools": ["add_node", "connect_nodes"],
    },
    "image_postprocess": {
        "description": "Image-space transforms, saving, and preview",
        "pure_types": {"IMAGE"},
        "agent_tools": ["add_node", "set_param", "add_inpaint_pass"],
    },
}

# ── Classification logic ──────────────────────────────────────────────────


def _extract_types(info: dict, direction: str) -> set[str]:
    """Extract type names from a node's input or output spec."""
    types: set[str] = set()
    if direction == "output":
        for t in info.get("output", []):
            if isinstance(t, str):
                types.add(t)
        return types

    for req_or_opt in ("required", "optional"):
        group = info.get("input", {}).get(req_or_opt, {})
        if not isinstance(group, dict):
            continue
        for _param_name, param_spec in group.items():
            if isinstance(param_spec, (list, tuple)) and param_spec:
                first = param_spec[0]
                if isinstance(first, str) and first.isupper():
                    types.add(first)
    return types


def classify_node(class_type: str, info: dict) -> list[str]:
    """Return the list of stage names a node belongs to."""
    output_types = _extract_types(info, "output")
    input_types = _extract_types(info, "input")
    category = (info.get("category") or "").lower()
    display_name = (info.get("display_name") or class_type).lower()

    stages: list[str] = []

    # Control preprocessors (check first — keyword match on category/name)
    ctrl_kw = STAGE_DEFINITIONS["control_preprocess"]["category_keywords"]
    if any(kw in category or kw in display_name for kw in ctrl_kw):
        stages.append("control_preprocess")

    # Loading: primary output is MODEL, CLIP, VAE, or CONTROL_NET
    load_out = STAGE_DEFINITIONS["loading"]["output_types"]
    if output_types & load_out:
        stages.append("loading")

    # Sampling: requires MODEL + CONDITIONING + LATENT, outputs LATENT
    samp_req = STAGE_DEFINITIONS["sampling"]["requires_inputs"]
    samp_out = STAGE_DEFINITIONS["sampling"]["output_types"]
    if samp_req <= input_types and (output_types & samp_out):
        stages.append("sampling")

    # Conditioning: outputs CONDITIONING (and is not a sampler)
    cond_out = STAGE_DEFINITIONS["conditioning"]["output_types"]
    if (output_types & cond_out) and "sampling" not in stages:
        stages.append("conditioning")

    # Decoding: requires LATENT + VAE, outputs IMAGE
    dec_req = STAGE_DEFINITIONS["decoding"]["requires_inputs"]
    dec_out = STAGE_DEFINITIONS["decoding"]["output_types"]
    if dec_req <= input_types and (output_types & dec_out):
        stages.append("decoding")

    # Latent ops: inputs and outputs are purely LATENT
    if output_types == {"LATENT"} and input_types <= {"LATENT"} and "sampling" not in stages:
        stages.append("latent_ops")

    # Image post-processing: pure IMAGE -> IMAGE (and not already classified)
    if not stages and output_types <= {"IMAGE", "MASK"} and "IMAGE" in input_types:
        stages.append("image_postprocess")

    # SaveImage / PreviewImage — these output nothing but consume IMAGE
    if not output_types and "IMAGE" in input_types:
        stages.append("image_postprocess")

    return stages


def explore(server_address: str) -> dict[str, Any]:
    """Query ComfyUI and return a stage map."""
    url = f"http://{server_address}/object_info"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            all_nodes: dict[str, dict] = json.loads(resp.read())
    except Exception as exc:
        print(f"[explore] Could not reach ComfyUI at {url}: {exc}", file=sys.stderr)
        print("[explore] Generating stage map from built-in definitions only.", file=sys.stderr)
        all_nodes = {}

    stage_nodes: dict[str, list[str]] = {s: [] for s in STAGE_DEFINITIONS}
    unclassified: list[str] = []

    for class_type, info in sorted(all_nodes.items()):
        matched = classify_node(class_type, info)
        if matched:
            for stage in matched:
                stage_nodes[stage].append(class_type)
        else:
            unclassified.append(class_type)

    stages_out: dict[str, Any] = {}
    for stage_name, defn in STAGE_DEFINITIONS.items():
        stages_out[stage_name] = {
            "description": defn["description"],
            "node_classes": sorted(stage_nodes[stage_name]),
            "agent_tools": defn["agent_tools"],
            "node_count": len(stage_nodes[stage_name]),
        }

    return {
        "server_address": server_address,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_nodes_discovered": len(all_nodes),
        "stages": stages_out,
        "unclassified_nodes": sorted(unclassified),
        "unclassified_count": len(unclassified),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Explore ComfyUI nodes and build stage map")
    parser.add_argument("--server", default="127.0.0.1:8188", help="ComfyUI server address")
    parser.add_argument("--output", "-o", default="stage_map.json", help="Output JSON path")
    args = parser.parse_args()

    stage_map = explore(args.server)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(stage_map, f, indent=2, ensure_ascii=False)

    total = stage_map["total_nodes_discovered"]
    unclass = stage_map["unclassified_count"]
    print(f"[explore] Discovered {total} nodes, classified {total - unclass}, "
          f"unclassified {unclass}")
    for name, data in stage_map["stages"].items():
        print(f"  {name}: {data['node_count']} nodes")
    print(f"[explore] Stage map written to {args.output}")


if __name__ == "__main__":
    main()
