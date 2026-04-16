
<div align="center">


# <img src="assets/logo.png" width="40" style="vertical-align: -25%; margin-right: -5px;"> GEMS: Agent-Native Multimodal Generation with Memory and Skills

<a href="https://arxiv.org/abs/2603.28088"><img src="https://img.shields.io/badge/arXiv-paper-b31b1b?logo=arxiv&logoColor=white" alt="Paper"></a>&nbsp;&nbsp;<a href="https://gems-gen.github.io"><img src="https://img.shields.io/badge/%F0%9F%8C%90%20Project-Page-2563eb" alt="Project Page"></a>&nbsp;&nbsp;
<a href="https://huggingface.co/papers/2603.28088"><img src="https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Paper-ffc107" alt="Paper"></a>



![Main Image](assets/main.png)

</div>


### Project Overview

GEMS ships with two interchangeable image-generation lines — both share
the same decompose / verify / refine / skill-routing pipeline, only the
`generate()` backend differs:

1. **HTTP line** (`agent/GEMS.py` + `infer.py`) — POSTs the prompt to a
   dedicated FastAPI server (`qwen_image.py` / `z_image.py`).
2. **ComfyUI line** (`agent/comfy_gems.py` + `infer_comfy.py`) — builds
   a full ComfyUI API-format workflow for the chosen model (Qwen-Image-2512,
   Z-Image-Turbo, FLUX.2 [klein] 9B, or LongCat-Image) and submits it
   to a running ComfyUI server. See [Infer (ComfyUI line)](#infer-comfyui-line).

```text
GEMS/
├── agent/
│   ├── server/                 # start server
│   │   ├── kimi.sh             # Kimi-K2.5
│   │   ├── qwen_image.py       # Qwen-Image-2512
│   │   └── z_image.py          # Z-Image-Turbo
│   ├── skills/
│   │   ├── aesthetic_drawing
│   │   │   └── SKILL.md
│   │   ├── creative_drawing
│   │   │   └── SKILL.md
│   │   ├── qwen-image-2512     # ComfyUI model skills
│   │   ├── z-image-turbo
│   │   ├── flux-klein-9b
│   │   ├── longcat-image
│   │   └── ...
│   ├── base_agent.py           # base Interfaces
│   ├── GEMS.py                 # core implementation (HTTP line)
│   ├── comfy_gems.py           # ComfyUI line (inherits GEMS)
│   ├── comfy_client.py         # ComfyUI HTTP client
│   └── comfy_workflow.py       # ComfyUI workflow templates
├── eval/                       # evalation for tasks
│   ├── ArtiMuse/
│   ├── CREA/
│   ├── GenEval2.py
│   └── ...
├── infer.py                    # HTTP line demo
├── infer_comfy.py              # ComfyUI line demo
└── ...
```


### Quick Start

```bash
git clone https://github.com/lcqysl/GEMS.git
cd GEMS
pip install requests litellm torch diffusers transformers fastapi uvicorn accelerate tqdm
```

---

### Setup: MLLM

GEMS uses an MLLM for reasoning, verification, and prompt refinement. Two options:

#### Option A — Cloud API via LiteLLM (recommended)

Supports Claude, GPT-4o, Gemini, and [any model LiteLLM covers](https://docs.litellm.ai/docs/providers). The default config uses **Claude Sonnet 4.6**.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

The model is set in `agent/base_agent.py`:
```python
LITELLM_MODEL = "anthropic/claude-sonnet-4-6"
```
Change this to switch providers (e.g. `"openai/gpt-4o"`, `"gemini/gemini-2.0-flash"`).

#### Option B — Self-hosted via SGLang

To run [Kimi-K2.5](https://huggingface.co/moonshotai/Kimi-K2.5) locally (requires 8× GPU):

```bash
pip install sglang

MODEL_PATH=/path/to/Kimi-K2.5 bash agent/server/kimi.sh
# Starts on http://localhost:30000
```

Then set `mllm_url` in `infer.py` and switch `base_agent.py` back to using the OpenAI-compatible client.

---

### Setup: Image Generation Server

GEMS supports [Qwen-Image-2512](https://huggingface.co/Qwen/Qwen-Image-2512) and [Z-Image-Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) as generators.

**Download model weights:**

```bash
# Qwen-Image-2512
huggingface-cli download Qwen/Qwen-Image-2512 --local-dir /path/to/Qwen-Image-2512

# Z-Image-Turbo (faster alternative)
huggingface-cli download Tongyi-MAI/Z-Image-Turbo --local-dir /path/to/Z-Image-Turbo
```

**Start the Qwen-Image server:**

```bash
MODEL_PATH=/path/to/Qwen-Image-2512 NUM_GPUS=1 python agent/server/qwen_image.py
# Starts on http://localhost:8000
```

- `NUM_GPUS`: number of GPUs to use (default: 1). Each GPU runs an independent worker; requests are load-balanced across them.
- `MODEL_PATH`: local path to the downloaded model weights.

**Start the Z-Image-Turbo server** (faster, 9 steps vs 50):

```bash
MODEL_PATH=/path/to/Z-Image-Turbo NUM_GPUS=1 PORT=8000 python agent/server/z_image.py
# Starts on http://localhost:8000 (default port: 8001)
```

**Verify the server is running:**

```bash
curl -X POST "http://localhost:8000/generate?prompt=a+cat+on+a+rooftop" --output test.png
```

---

### Infer

Edit `infer.py` to set your image generation server URL, then run:

```python
# infer.py
gen_url = "http://localhost:8000/generate"   # Qwen-Image (port 8000) or Z-Image-Turbo (port 8001)
max_iterations = 5
```

```bash
python infer.py
```

Output is saved to `infer_results/test_output.png`.

**How it works:** GEMS decomposes the prompt into verification questions, generates an image, checks each requirement, and iteratively refines the prompt based on failures — repeating up to `max_iterations` rounds.

---

### Infer (ComfyUI line)

GEMS ships a second generation line that produces **ComfyUI API-format
workflows** and submits them to a running ComfyUI server.  The
decompose → generate → verify → refine loop from the HTTP line is
preserved verbatim (inherited from `GEMS`) — only `generate()` is
replaced: instead of `POST /generate?prompt=...` it builds a full
workflow dict, submits to ComfyUI's `/prompt`, polls `/history`, and
downloads the output via `/view`.

**Supported models (one base-workflow template each):**

| Model | `model=` value | Topology highlights |
|---|---|---|
| Qwen-Image-2512 | `qwen-image-2512` | 20B MMDiT, FP8; `ModelSamplingAuraFlow` → `KSampler` (steps=50, cfg=4.0, euler/simple); 1328×1328 |
| Z-Image-Turbo | `z-image-turbo` | 6B S3-DiT, BF16; `ConditioningZeroOut` for negatives; `KSampler` (steps=8, cfg=1, res_multistep); 1024×1024 |
| FLUX.2 [klein] 9B | `flux-klein-9b` | `SamplerCustomAdvanced` + `CFGGuider` + `Flux2Scheduler` + `RandomNoise` + `KSamplerSelect`; 4 steps; 1024×1024 |
| LongCat-Image | `longcat-image` | 6B DiT, BF16; `FluxGuidance` on both positive/negative + `CFGNorm`; `KSampler` (steps=20, cfg=4); 1024×1024 |

Each model has a corresponding `SKILL.md` under `agent/skills/<model>/`
(imported as-is from `comfyclaw`, YAML-frontmatter format) so the
`SkillManager` / `plan()` step can route the user's prompt through the
model's own recipe.

**Prerequisites:**

* A reachable ComfyUI server (version with the right custom nodes; we
  tested against ComfyUI 0.19+ with native `QwenImage*` / `FluxGuidance`
  / `CFGNorm` / `Flux2Scheduler` support).
* Model weights / text encoders / VAE for the chosen model installed at
  the standard `ComfyUI/models/...` paths — the exact filenames expected
  by each workflow template are listed in the corresponding
  `agent/skills/<model>/SKILL.md`.
* `ANTHROPIC_API_KEY` (or any other LiteLLM-supported provider, see
  `agent/base_agent.py`) for the MLLM used by decompose / verify /
  refine.

**Quick run:**

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export COMFYUI_SERVER=127.0.0.1:8188      # host:port of ComfyUI
export GEMS_COMFY_MODEL=z-image-turbo     # or qwen-image-2512 / flux-klein-9b / longcat-image
export GEMS_MAX_ITERATIONS=5
python infer_comfy.py
```

Output:

* `infer_results/test_output_comfy.png` — final (best) image
* `infer_results/workflows/workflow_NNN.json` — every workflow submitted
  this run, pretty-printed for inspection / replay in the ComfyUI UI

**Programmatic use:**

```python
from agent.comfy_gems import ComfyGEMS

agent = ComfyGEMS(
    model="qwen-image-2512",           # or alias: "qwen", "z-image", "flux-klein", "longcat", ...
    comfyui_server="127.0.0.1:8188",
    max_iterations=5,
    workflow_log_dir="run_workflows",  # optional: dump every submitted workflow
    seed=42,                           # optional: pin KSampler / RandomNoise seed
    default_negative=None,             # optional: override per-model negative prompt
    workflow_timeout=600,              # optional: seconds to wait for one ComfyUI job
)
image_bytes = agent.run({"prompt": "a cozy cabin in a snowy pine forest at dusk"})

# Build (but don't submit) the workflow, e.g. for offline inspection:
wf_dict = agent.build_workflow("a cozy cabin in a snowy pine forest at dusk")
```

**Scope of this line (by design):** only `generate()` is new — the
refine loop still edits only the positive prompt, verification is still
the stock MLLM yes/no decomposition, and the workflow itself is NOT
topologically evolved (no LoRA / ControlNet auto-insertion, no sampler
LLM-tuning, no repair loop).  Use `comfyclaw` if you want topology
evolution on top of ComfyUI.

---

### Evaluation

Images are first generated with GEMS, then scored with task-specific methods.

**GenEval2:**

First, download the benchmark data:

```bash
# Option A — from Hugging Face
hf download Jialuo21/GenEval2 --repo-type dataset --local-dir /path/to/GenEval2

# Option B — from GitHub
git clone https://github.com/facebookresearch/GenEval2.git /path/to/GenEval2
```

Then set `DATA_PATH` and `OUTPUT_DIR` at the top of `eval/GenEval2.py` to point to your local copy, and run:

```bash
python eval/GenEval2.py \
    --name my_run \
    --agent gems \
    --max_iterations 5
```

Set `gen_url` and `mllm_url` at the top of `eval/GenEval2.py` before running.

**CREA:**

```bash
python eval/CREA/CREA.py \
    --name my_run \
    --agent gems \
    --max_iterations 5 \
    --n_samples 25
```

**ArtiMuse:**

```bash
python eval/ArtiMuse/gen_artimuse.py \
    --gen_url http://localhost:8000/generate \
    --mllm_url http://localhost:30000/v1 \
    --max_iterations 5
```

**Note:** Occasional server errors (e.g., timeouts) may result in missing outputs for a few tasks. Simply re-run — the scripts automatically skip already-completed items.

We provide full evaluation code for **CREA** and **ArtiMuse**. For other tasks, evaluations follow their official settings.


### Skills
![Skill](assets/skill_demo.png)

Our Skills are summarized from previous works and tested on downstream tasks. You can also add your own by referring to `agent/skills`.

Each skill should be organized as follows:

```text
agent/skills/
└── <skill_id>/             # Unique folder name (used as Skill ID)
    └── SKILL.md            # Skill definition file
```

`SkillManager` accepts **either** of the two formats below (auto-detected):

**Format A — legacy GEMS template:**

```markdown
# Skill: <Name>

## Description
Provide a concise summary of what this skill does.

## Instructions
Provide detailed domain-specific guidance, prompts, or constraints here.
The code will capture all content remaining below this header.
```

**Format B — Agent-Skills YAML frontmatter** (used by the ComfyUI-line
model skills imported from comfyclaw):

```markdown
---
name: <skill-id>
description: >-
  One-or-more-line description of the skill.
---

The entire body below the closing `---` becomes the skill's
instructions.
```

Both formats surface the folder name as the `SKILL_ID` in the planner
manifest.

### Citation
If you find our work useful, please consider citing:
```code
@article{he2026gems,
  title={GEMS: Agent-Native Multimodal Generation with Memory and Skills},
  author={He, Zefeng and Huang, Siyuan and Qu, Xiaoye and Li, Yafu and Zhu, Tong and Cheng, Yu and Yang, Yang},
  journal={arXiv preprint arXiv:2603.28088},
  year={2026}
}
```