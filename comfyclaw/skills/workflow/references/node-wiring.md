# Output Slot Reference

When wiring nodes via `add_node(... input_name=[src_node_id, OUTPUT_SLOT])`,
use the correct output slot index. Wrong slot = ComfyUI 400 error.

| Node class | Slot 0 | Slot 1 | Slot 2 |
|---|---|---|---|
| **CheckpointLoaderSimple** | MODEL | CLIP | VAE |
| **UNETLoader** | MODEL | — | — |
| **CLIPLoader** | CLIP | — | — |
| **DualCLIPLoader** | CLIP | — | — |
| **VAELoader** | VAE | — | — |
| **LoraLoader** | MODEL | CLIP | — |
| **LoraLoaderModelOnly** | MODEL | — | — |
| **CLIPTextEncode** | CONDITIONING | — | — |
| **EmptyLatentImage** | LATENT | — | — |
| **EmptySD3LatentImage** | LATENT | — | — |
| **KSampler** | LATENT | — | — |
| **VAEDecode** | IMAGE | — | — |
| **ModelSamplingAuraFlow** | MODEL | — | — |
| **FluxGuidance** | CONDITIONING | — | — |
| **ControlNetLoader** | CONTROL_NET | — | — |
| **ControlNetApplyAdvanced** | positive (CONDITIONING) | negative (CONDITIONING) | — |
| **LatentUpscaleBy** | LATENT | — | — |

## Common wiring mistakes

- CheckpointLoaderSimple: CLIP is slot **1** (not 0), VAE is slot **2** (not 1)
- UNETLoader: only has slot **0** (MODEL) — no CLIP or VAE outputs
- KSampler output is LATENT at slot **0** — feed to VAEDecode `samples`
- VAEDecode output is IMAGE at slot **0** — feed to SaveImage `images`
