"""Entry point for the GEMS ComfyUI line.

GEMS supports two image-generation lines:

1. The original HTTP line — ``infer.py`` (calls ``qwen_image.py`` /
   ``z_image.py``).
2. The ComfyUI line — *this file*.  Each iteration of the GEMS
   decompose→verify→refine loop builds a complete ComfyUI API-format
   workflow for the chosen model and submits it to a running ComfyUI
   server; the rest of the GEMS pipeline (skill routing, MLLM verifier,
   prompt refinement, experience summarisation) is unchanged.

Supported models:

* ``qwen-image-2512``   — Qwen-Image-2512
* ``z-image-turbo``     — Z-Image-Turbo
* ``flux-klein-9b``     — FLUX.2 [klein] 9B
* ``longcat-image``     — LongCat-Image

Before running, make sure:

* A ComfyUI server is reachable at ``COMFYUI_SERVER`` with the model
  weights + text encoders + VAE for the chosen model installed at the
  usual ``ComfyUI/models/...`` paths (see each SKILL.md under
  ``agent/skills/`` for exact filenames).
* ``ANTHROPIC_API_KEY`` (or whichever provider you configure in
  ``agent/base_agent.py``) is exported for the MLLM.
"""

import os

from agent.comfy_gems import ComfyGEMS

TEST_PROMPT = (
    "A book floating in the sky, creative and cool concept, "
    "make it look artistic and dreamy."
)

SAVE_DIR = "infer_results"
COMFYUI_SERVER = os.environ.get("COMFYUI_SERVER", "127.0.0.1:8188")
MODEL = os.environ.get("GEMS_COMFY_MODEL", "qwen-image-2512")
MAX_ITERATIONS = int(os.environ.get("GEMS_MAX_ITERATIONS", "5"))

agent = ComfyGEMS(
    model=MODEL,
    comfyui_server=COMFYUI_SERVER,
    max_iterations=MAX_ITERATIONS,
    workflow_log_dir=os.path.join(SAVE_DIR, "workflows"),
)


def test_single_agent():
    os.makedirs(SAVE_DIR, exist_ok=True)

    item = {"prompt": TEST_PROMPT}
    print(f"Image model : {agent.model_display_name} ({agent.image_model})")
    print(f"MLLM        : {agent.model}")
    print(f"ComfyUI     : {COMFYUI_SERVER}")
    print(f"Prompt: {TEST_PROMPT}")

    try:
        image_bytes = agent.run(item)
        save_path = os.path.join(SAVE_DIR, "test_output_comfy.png")
        with open(save_path, "wb") as f:
            f.write(image_bytes)
        print(f"Saved image   → {save_path}")
        print(f"Workflows in  → {agent.workflow_log_dir}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_single_agent()
