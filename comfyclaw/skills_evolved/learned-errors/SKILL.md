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
3. **Integer inputs STRICT TYPE** - MUST be bare integers (512, 20, 1) - NEVER floats (1.0), strings ("512"), null, or arrays
   - **COMMON ERROR**: Passing `[value]` instead of `value` - unwrap single-element arrays
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
CLIPTextEncode(positive)[0] → KSampler.positive
CLIPTextEncode(negative)[0] → KSampler.negative
EmptyLatentImage[0] → KSampler.latent_image
KSampler[0] → VAEDecode.samples
VAEDecode[0] → SaveImage.images
```

## Required Inputs by Node Type

### KSampler **[COMMONLY INCOMPLETE]**
- `model`: MODEL (checkpoint slot 0) - **REQUIRED**
- `positive`: CONDITIONING (CLIPTextEncode[0]) - **REQUIRED**
- `negative`: CONDITIONING (CLIPTextEncode[0]) - **REQUIRED**
- `latent_image`: LATENT (EmptyLatentImage[0]/VAEEncode[0]) - **REQUIRED**
- `seed`: INT >= 0 - **REQUIRED, bare integer only**
- `steps`: INT > 0 - **REQUIRED, bare integer only**
- `cfg`: FLOAT (1.0-20.0) - **REQUIRED**
- `sampler_name`: STRING - **REQUIRED** (e.g., "euler", "dpmpp_2m")
- `scheduler`: STRING - **REQUIRED** (e.g., "normal", "karras", "exponential")
- `denoise`: FLOAT (0.0-1.0) - **REQUIRED**

### VAEDecode / VAEEncode **[MOST COMMONLY MISSING]**
- `samples` (VAEDecode) / `pixels` (VAEEncode): LATENT/IMAGE - **REQUIRED**
- `vae`: VAE (checkpoint slot 2 or VAELoader[0]) - **REQUIRED, ALWAYS CONNECT THIS**

### CLIPTextEncode
- `clip`: CLIP (checkpoint slot 1) - **REQUIRED**
- `text`: STRING (non-empty prompt) - **REQUIRED**

### EmptyLatentImage
- `width`: INT (must be multiple of 8) - **REQUIRED, bare integer**
- `height`: INT (must be multiple of 8) - **REQUIRED, bare integer**
- `batch_size`: INT >= 1 - **REQUIRED, bare integer**

### SaveImage / PreviewImage
- `images`: IMAGE (VAEDecode[0]/LoadImage[0]) - **REQUIRED**

### LoadImage
- `image`: STRING (filename only) - **REQUIRED**
- **Output slot 0: IMAGE** (use for image connections)

## Common Error Patterns & Fixes

**"Failed to convert input to INT"** ← RECURRING ERROR
→ Integer parameter has float (1.0), string ("1"), null, or **array ([512])**
→ **FIX**: Use bare integers: `512` not `512.0` or `[512]`, `1` not `"1"` or `[1]`
→ **CHECK**: width, height, steps, seed, batch_size - ALL must be unwrapped integers

**"Required input is missing: vae"** ← MOST COMMON
→ VAEDecode/VAEEncode `vae` input disconnected
→ **FIX**: Wire CheckpointLoaderSimple[2] → node.vae

**"Required input is missing: positive/negative"**
→ KSampler missing CONDITIONING inputs
→ **FIX**: Wire CLIPTextEncode[0] → KSampler.positive AND KSampler.negative

**"Value -1 smaller than min of 0"**
→ Seed parameter is negative
→ **FIX**: ALWAYS use seed >= 0 (e.g., 42, 123456) - NEVER -1

**"'str' object has no attribute 'shape'"**
→ IMAGE input received string instead of IMAGE tensor
→ **FIX**: Use LoadImage[0] → target.images (NEVER pass raw strings)

**"Prompt has no outputs"**
→ Missing SaveImage/PreviewImage OR images input disconnected
→ **FIX**: Add SaveImage and wire VAEDecode[0] → SaveImage.images

## Type Compatibility Reference

| Output Type | Source Nodes (slot) | Compatible Inputs |
|-------------|---------------------|-------------------|
| MODEL | CheckpointLoaderSimple[0] | KSampler.model |
| CLIP | CheckpointLoaderSimple[1] | CLIPTextEncode.clip |
| VAE | CheckpointLoaderSimple[2], VAELoader[0] | VAEDecode.vae, VAEEncode.vae |
| CONDITIONING | CLIPTextEncode[0] | KSampler.positive/negative |
| LATENT | KSampler[0], EmptyLatentImage[0], VAEEncode[0] | VAEDecode.samples |
| IMAGE | VAEDecode[0], LoadImage[0] | VAEEncode.pixels, SaveImage.images |

## Pre-Submission Checklist

1. ✓ **ALL integers are bare values** - NEVER floats, strings, null, or arrays like `[512]`
2. ✓ **SCAN FOR ALL VAE NODES** - Every VAEDecode/VAEEncode has `vae` connected to checkpoint[2]
3. ✓ **KSampler complete** - positive/negative/sampler_name/scheduler all set
4. ✓ **Seed >= 0** - NEVER -1 or negative
5. ✓ **IMAGE inputs use LoadImage[0]** - NEVER raw strings
6. ✓ **Output node exists** - SaveImage with VAEDecode[0] → images
7. ✓ **Dimensions multiple of 8** - width/height for EmptyLatentImage