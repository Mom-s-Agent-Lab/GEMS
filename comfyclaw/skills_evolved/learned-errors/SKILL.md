---
name: learned-errors
description: Read this when ComfyUI returns validation errors, type mismatches, or workflow execution failures. Contains specific wiring rules, slot indices, and parameter constraints to prevent common connection errors.
---

# ComfyUI Workflow Error Prevention

## CRITICAL: Pre-Submission Validation - CHECK EVERY TIME

**TOP 5 FAILURE CAUSES** - Verify before submission:

1. **VAE MUST BE CONNECTED** - VAEDecode/VAEEncode `vae` input is THE MOST FORGOTTEN connection
   - Always wire CheckpointLoaderSimple[2] → VAEDecode.vae AND VAEEncode.vae
   - **EVERY VAE node needs this** - no exceptions, double-check ALL VAE nodes
2. **KSampler positive/negative CONDITIONING** - MUST wire CLIPTextEncode outputs to BOTH inputs
   - NEVER leave positive or negative disconnected - validation will fail immediately
3. **Integer inputs** - MUST be bare integers (512, 20, 1) - NEVER floats (1.0), strings ("512"), or null
4. **IMAGE vs STRING** - Image inputs REQUIRE IMAGE tensors - use LoadImage[0] for file paths, NEVER raw strings
5. **Output nodes required** - Workflow MUST have SaveImage/PreviewImage with images connected

## Standard Checkpoint Loader Output Slots (MEMORIZE)

**CheckpointLoaderSimple** outputs:
- **Slot 0: MODEL** → KSampler.model, LoRA loaders
- **Slot 1: CLIP** → CLIPTextEncode.clip (positive AND negative encoders)
- **Slot 2: VAE** → VAEDecode.vae, VAEEncode.vae

**Standard workflow wiring**:
```
CheckpointLoaderSimple[0] → KSampler.model
CheckpointLoaderSimple[1] → CLIPTextEncode.clip (BOTH positive/negative)
CheckpointLoaderSimple[2] → VAEDecode.vae (AND VAEEncode.vae if used)
CLIPTextEncode(positive) → KSampler.positive
CLIPTextEncode(negative) → KSampler.negative
EmptyLatentImage[0] → KSampler.latent_image
KSampler[0] → VAEDecode.samples
VAEDecode[0] → SaveImage.images
```

## Required Inputs by Node Type

### KSampler **[COMMONLY INCOMPLETE]**
- `model`: MODEL (checkpoint slot 0) - **REQUIRED**
- `positive`: CONDITIONING (CLIPTextEncode[0]) - **REQUIRED, NEVER leave disconnected**
- `negative`: CONDITIONING (CLIPTextEncode[0]) - **REQUIRED, NEVER leave disconnected**
- `latent_image`: LATENT (EmptyLatentImage[0]/VAEEncode[0]) - **REQUIRED**
- `seed`: INT >= 0 - **REQUIRED, NEVER -1 or negative**
- `steps`: INT > 0 - **REQUIRED**
- `cfg`: FLOAT (1.0-20.0) - **REQUIRED**
- `sampler_name`: STRING - **REQUIRED** (e.g., "euler", "dpmpp_2m")
- `scheduler`: STRING - **REQUIRED** (e.g., "normal", "karras", "exponential")
- `denoise`: FLOAT (0.0-1.0) - **REQUIRED**

### VAEDecode / VAEEncode **[MOST COMMONLY MISSING - RECHECK EVERY NODE]**
- `samples` (VAEDecode) / `pixels` (VAEEncode): LATENT/IMAGE - **REQUIRED**
- `vae`: VAE (checkpoint slot 2 or VAELoader[0]) - **REQUIRED, ALWAYS CONNECT THIS**
- **SCAN ENTIRE WORKFLOW**: Find ALL VAEDecode/VAEEncode nodes and verify EACH has `vae` connected

### CLIPTextEncode
- `clip`: CLIP (checkpoint slot 1) - **REQUIRED**
- `text`: STRING (non-empty prompt) - **REQUIRED, NEVER null/empty**

### SaveImage / PreviewImage
- `images`: IMAGE (VAEDecode[0]/LoadImage[0]) - **REQUIRED, must be IMAGE type, NEVER string path**

### LoadImage
- `image`: STRING (filename only, not full path) - **REQUIRED**
- **Output slot 0: IMAGE** (use this for image connections) - **ALWAYS use LoadImage[0] for IMAGE inputs**
- Output slot 1: MASK

## Type Compatibility Reference

| Output Type | Source Nodes (slot) | Compatible Inputs |
|-------------|---------------------|-------------------|
| MODEL | CheckpointLoaderSimple[0] | KSampler.model |
| CLIP | CheckpointLoaderSimple[1] | CLIPTextEncode.clip |
| VAE | CheckpointLoaderSimple[2], VAELoader[0] | VAEDecode.vae, VAEEncode.vae |
| CONDITIONING | CLIPTextEncode[0] | KSampler.positive/negative |
| LATENT | KSampler[0], EmptyLatentImage[0], VAEEncode[0] | VAEDecode.samples |
| IMAGE | VAEDecode[0], LoadImage[0] | VAEEncode.pixels, SaveImage.images |

## Common Error Patterns & Fixes

**"Required input is missing: vae"** ← MOST COMMON ERROR - HAPPENS REPEATEDLY
→ VAEDecode/VAEEncode `vae` input disconnected
→ **FIX**: Wire CheckpointLoaderSimple[2] → node.vae
→ **PREVENTION**: Search workflow for ALL VAEDecode/VAEEncode nodes - check EACH one individually

**"Required input is missing: positive/negative"**
→ KSampler missing CONDITIONING inputs
→ **FIX**: Wire CLIPTextEncode[0] → KSampler.positive AND KSampler.negative

**"Required input is missing: scheduler" / "sampler_name"**
→ KSampler missing required string parameters
→ **FIX**: Set `sampler_name` (e.g., "euler") and `scheduler` (e.g., "normal") - these are REQUIRED

**"Value -1 smaller than min of 0"** ← COMMON SEED ERROR
→ Seed parameter is negative (often default -1)
→ **FIX**: ALWAYS use seed >= 0 (e.g., 42, 123456) - NEVER -1

**"Failed to convert input to INT"**
→ Integer parameter has float (1.0), string ("1"), or null
→ **FIX**: Use bare integers: `512` not `512.0`, `1` not `"1"`

**"'str' object has no attribute 'shape'"** ← RUNTIME ERROR
→ IMAGE input received string path instead of IMAGE tensor
→ **FIX**: Use LoadImage node and wire LoadImage[0] → target.images (NEVER pass raw strings to IMAGE inputs)

**"Prompt has no outputs"**
→ Missing SaveImage/PreviewImage OR images input disconnected
→ **FIX**: Add SaveImage and wire VAEDecode[0] → SaveImage.images

## Pre-Submission Checklist

1. ✓ **SCAN FOR ALL VAE NODES** - Find every VAEDecode/VAEEncode, verify EACH has `vae` connected to checkpoint[2]
2. ✓ **KSampler positive/negative connected** - BOTH wired to CLIPTextEncode[0]
3. ✓ **KSampler sampler_name/scheduler set** - BOTH are required string parameters
4. ✓ **Seed is >= 0** - NEVER use -1 or negative values
5. ✓ **IMAGE inputs use LoadImage[0]** - NEVER pass raw strings to IMAGE slots
6. ✓ **Output node exists** - SaveImage/PreviewImage with VAEDecode[0] → images
7. ✓ All