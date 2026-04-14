# Model Architecture Recipes

## Architecture Detection

Match model filename to architecture:

| Filename pattern | Architecture | Recipe |
|---|---|---|
| `*sd15*`, `*sd_1*`, `dreamshaper*`, `realistic*`, `deliberate*` | SD 1.5 | A |
| `*sdxl*`, `*sd_xl*`, `juggernaut*`, `zavychroma*` | SDXL | B |
| `*flux*` | Flux | C |
| `*qwen_image*` | Qwen-Image-2512 | D |
| `*hunyuan*` | HunyuanDiT | E |
| `*sd3*`, `*sd_3*` | SD 3.x | F |

Priority when multiple models available: Flux > SDXL > Qwen > SD 1.5

## Recipe A — SD 1.5

| Parameter | Value |
|---|---|
| Resolution | 512x512 (max 768x768) |
| Steps | 20 |
| CFG | 7.0 |
| Sampler | `euler_ancestral` |
| Scheduler | `normal` |
| Latent node | `EmptyLatentImage` |
| Loader | `CheckpointLoaderSimple` |

LCM variant: steps=6, cfg=2.0, sampler=`lcm`, scheduler=`sgm_uniform`

## Recipe B — SDXL

| Parameter | Value |
|---|---|
| Resolution | 1024x1024 |
| Steps | 25 |
| CFG | 7.0 |
| Sampler | `dpmpp_2m` |
| Scheduler | `karras` |
| Latent node | `EmptyLatentImage` |
| Loader | `CheckpointLoaderSimple` |

Resolution buckets: 1024x1024, 1344x768, 768x1344, 1152x896, 896x1152

## Recipe C — Flux

| Parameter | Value |
|---|---|
| Resolution | 1024x1024 |
| Steps | 20 |
| CFG | 1.0 (guidance via FluxGuidance node, default 3.5) |
| Sampler | `euler` |
| Scheduler | `simple` |
| Latent node | `EmptySD3LatentImage` |
| Loader | `UNETLoader` + `DualCLIPLoader` (type=flux) + `VAELoader` |
| weight_dtype | `fp8_e4m3fn` (use `default` on MPS) |

Flux does NOT use negative prompts. Uses `FluxGuidance` node for guidance.

## Recipe D — Qwen-Image-2512

See `references/qwen-image.md` for full details.

| Parameter | Value (Lightning) | Value (Standard) |
|---|---|---|
| Resolution | 1328x1328 | 1328x1328 |
| Steps | 4 | 50 |
| CFG | 1.0 | 4.0 |
| Sampler | `euler` | `euler` |
| Scheduler | `simple` | `simple` |
| Latent node | `EmptySD3LatentImage` | `EmptySD3LatentImage` |
| Extra node | `ModelSamplingAuraFlow` (shift=3.1) | Same |
| Loader | `UNETLoader` + `CLIPLoader` (type=qwen_image) + `VAELoader` | Same |

## Recipe E — HunyuanDiT

| Parameter | Value |
|---|---|
| Resolution | 1024x1024 |
| Steps | 30 |
| CFG | 6.0 |
| Sampler | `euler` |
| Scheduler | `normal` |
| Latent node | `EmptySD3LatentImage` |
| Loader | `UNETLoader` + `DualCLIPLoader` (type=hunyuan_dit) + `VAELoader` |

## Recipe F — SD 3.x

| Parameter | Value |
|---|---|
| Resolution | 1024x1024 |
| Steps | 28 |
| CFG | 4.5 |
| Sampler | `euler` |
| Scheduler | `sgm_uniform` |
| Latent node | `EmptySD3LatentImage` |
| Loader | `CheckpointLoaderSimple` |
