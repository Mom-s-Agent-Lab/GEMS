"""Offline smoke test for ``ComfyGEMSAgentic``.

Simulates a tool-call sequence (as a real LLM would emit) and confirms the
dispatcher builds a valid ComfyUI graph without needing a live LLM or
ComfyUI server.

Run: ``python -m agent._demo_comfy_gems_agentic`` from the GEMS repo root
(with the sibling ``comfyclaw/`` checkout on disk).
"""
from __future__ import annotations

import sys
import os

# Make sibling comfyclaw importable when the package isn't pip-installed.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "comfyclaw")))

from agent.comfy_gems_agentic import ComfyGEMSAgentic, WorkflowManager


def simulate_tool_calls() -> None:
    """Walk through a fake 'LLM tool-use trace' and inspect the result."""
    agent = ComfyGEMSAgentic.__new__(ComfyGEMSAgentic)
    agent.comfyui_server = "127.0.0.1:8188"
    agent._wm = WorkflowManager({})
    wm = agent._wm

    scripted = [
        ("inspect_workflow", {}),
        ("add_node", {"class_type": "UNETLoader", "nickname": "UNET",
                      "inputs": {"unet_name": "z_image_turbo_bf16.safetensors",
                                 "weight_dtype": "default"}}),
        ("add_node", {"class_type": "CLIPLoader", "nickname": "CLIP",
                      "inputs": {"clip_name": "qwen_3_4b.safetensors",
                                 "type": "lumina2", "device": "default"}}),
        ("add_node", {"class_type": "VAELoader", "nickname": "VAE",
                      "inputs": {"vae_name": "ae.safetensors"}}),
        ("add_node", {"class_type": "CLIPTextEncode", "nickname": "Positive",
                      "inputs": {"clip": ["2", 0], "text": ""}}),
        ("add_node", {"class_type": "CLIPTextEncode", "nickname": "Negative",
                      "inputs": {"clip": ["2", 0], "text": ""}}),
        ("add_node", {"class_type": "EmptySD3LatentImage", "nickname": "Latent",
                      "inputs": {"width": 1024, "height": 1024, "batch_size": 1}}),
        ("add_node", {"class_type": "KSampler", "nickname": "KSampler",
                      "inputs": {"model": ["1", 0], "positive": ["4", 0],
                                 "negative": ["5", 0], "latent_image": ["6", 0],
                                 "seed": 42, "steps": 8, "cfg": 1.0,
                                 "sampler_name": "res_multistep",
                                 "scheduler": "simple", "denoise": 1.0}}),
        ("add_node", {"class_type": "VAEDecode", "nickname": "Decode",
                      "inputs": {"samples": ["7", 0], "vae": ["3", 0]}}),
        ("add_node", {"class_type": "SaveImage", "nickname": "Save",
                      "inputs": {"images": ["8", 0],
                                 "filename_prefix": "GEMS_Agentic"}}),
        ("set_prompt", {"positive_text": "a red fox at dawn, photorealistic",
                        "negative_text": "blurry, lowres"}),
        ("validate_workflow", {}),
        ("finalize_workflow", {"rationale": "Minimal z-image pipeline built from scratch."}),
    ]

    print("=" * 60)
    print("Simulated tool-use trace")
    print("=" * 60)
    for name, args in scripted:
        out, stop, extra = agent._dispatch(name, args, wm)
        print(f"\n>>> {name}({args})")
        print(out)
        if stop:
            print(f"\n--- FINALIZED: {(extra or {}).get('rationale')}")
            break

    print("\n" + "=" * 60)
    print("Final workflow")
    print("=" * 60)
    print(WorkflowManager.summarize(wm.workflow))

    errs = WorkflowManager.validate_graph(wm.workflow)
    assert not errs, f"Expected valid graph, got errors: {errs}"
    print("\n✅ Graph validates cleanly.")

    # Confirm prompts landed in the encoders.
    for nid, node in wm.workflow.items():
        if node["class_type"] == "CLIPTextEncode":
            print(f"  Node {nid} ({node['_meta']['title']}): text = "
                  f"{node['inputs'].get('text')!r}")


if __name__ == "__main__":
    simulate_tool_calls()
