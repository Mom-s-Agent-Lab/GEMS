---
name: workflow
description: >-
  Build and execute ComfyUI image generation workflows step-by-step with
  stage-gated tool disclosure. Use when constructing a new pipeline from
  scratch, evolving an existing topology, or generating images through the
  full pipeline cycle: planning -> construction -> conditioning ->
  enhancement -> finalization. This skill guides the agent through each
  stage, exposing only the relevant tools at each phase to reduce errors
  and improve workflow correctness. Always use this skill for structured
  image generation.
license: MIT
metadata:
  author: comfyclaw
  version: "1.0.0"
---

# Workflow — Stage-Gated Image Generation Pipeline

This skill orchestrates image generation through a structured 5-stage
pipeline. At each stage, only the tools relevant to that phase are
available, reducing hallucinated tool calls and improving correctness.

## Pipeline stages

```
Planning ──► Construction ──► Conditioning ──► Enhancement ──► Finalization
   │              │                │                │               │
   │ Understand   │ Build the      │ Set prompts    │ Add LoRA,     │ Validate
   │ goal, query  │ node graph     │ and controls   │ hires-fix,    │ and submit
   │ models,      │ node-by-node   │                │ inpaint       │
   │ read skills  │                │                │               │
```

### Stage 1 — Planning

**Available tools**: `inspect_workflow`, `report_evolution_strategy`,
`read_skill`, `query_available_models`, `explore_nodes`, `transition_stage`

**Actions**:
1. Call `report_evolution_strategy` to declare your plan
2. Call `inspect_workflow` to see the current topology
3. If workflow is empty: call `query_available_models("checkpoints")` and
   `query_available_models("diffusion_models")` to discover models
4. Read relevant skill references (see `references/` directory):
   - `references/model-configs.md` for sampler/scheduler defaults
   - `references/node-wiring.md` for output slot reference
   - `references/qwen-image.md` for Qwen-specific config
5. Call `transition_stage("construction")` when planning is done

### Stage 2 — Construction

**Available tools**: `add_node`, `connect_nodes`, `delete_node`,
`set_param`, `inspect_workflow`, `query_available_models`, `read_skill`,
`transition_stage`

**Actions**:
1. Build the base pipeline node-by-node following the architecture recipe
   matching your detected model (see `references/model-configs.md`)
2. Use EXACT filenames from `query_available_models` — never guess
3. Wire nodes using output slot indices from `references/node-wiring.md`
4. Call `transition_stage("conditioning")` when the graph is wired

### Stage 3 — Conditioning

**Available tools**: `set_prompt`, `add_regional_attention`,
`add_controlnet`, `set_param`, `inspect_workflow`, `read_skill`,
`transition_stage`

**Actions**:
1. Call `set_prompt` with a detailed, professional positive prompt:
   `[subject & scene], [style], [lighting], [camera/lens], [quality boosters]`
2. Set a strong negative prompt
3. Add regional attention if the scene has distinct foreground/background
4. Add ControlNet if structural guidance is needed
5. Call `transition_stage("enhancement")` when conditioning is complete

### Stage 4 — Enhancement

**Available tools**: `add_lora_loader`, `add_hires_fix`,
`add_inpaint_pass`, `set_param`, `add_node`, `connect_nodes`,
`delete_node`, `inspect_workflow`, `query_available_models`, `read_skill`,
`transition_stage`

**Actions** (apply based on verifier feedback or preemptive quality):
1. Add LoRA for style/detail/anatomy improvement
2. Add hires-fix for resolution upscaling
3. Add inpaint pass for localised artifact repair
4. Tune sampler parameters (steps, CFG, seed) if needed
5. Call `transition_stage("finalization")` when enhancements are done

### Stage 5 — Finalization

**Available tools**: `validate_workflow`, `finalize_workflow`,
`inspect_workflow`, `set_param`, `delete_node`, `connect_nodes`,
`transition_stage`

**Actions**:
1. Call `validate_workflow` to check for errors
2. Fix any issues found (may need to `transition_stage("construction")`)
3. Call `finalize_workflow` with a rationale summary

## When evolving an existing workflow (iteration > 1)

On subsequent iterations after verifier feedback:
1. Start in **Planning** — read verifier feedback, declare strategy
2. Jump directly to the relevant stage:
   - Prompt issues → `transition_stage("conditioning")`
   - Need LoRA/hires-fix → `transition_stage("enhancement")`
   - Structural graph errors → `transition_stage("construction")`
3. Make targeted changes, then finalize

## Reference files

Read these for detailed configuration data:
- `references/model-configs.md` — Architecture recipes, sampler defaults, resolution buckets
- `references/node-wiring.md` — Output slot indices for every node class
- `references/qwen-image.md` — Qwen-Image-2512 specific pipeline configuration
