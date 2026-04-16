---
name: counting-objects
description: >-
  Enforce precise object counts and handle multiple distinct object types in a single scene using regional conditioning, explicit numerical layout prompts, and count-specific negative prompts.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

## When to Use
Trigger when:
- User specifies exact counts ("three dogs", "five cars", "four rabbits")
- Prompt contains multiple distinct object types ("a backpack and a pig", "cars and a kangaroo")
- Verifier reports wrong count, missing objects, or merged objects
- fix_strategy contains "add_regional_prompt" or "enforce_count"

## Core Strategy
Diffusion models struggle with counts >3 and with keeping different object types visually distinct. Use regional conditioning to isolate each object type and explicit spatial layout to prevent merging.

## Implementation Steps

### 1. Separate Object Types with Regional Conditioning
For prompts with multiple object types ("X and Y"):
- Use ConditioningSetArea or regional prompt nodes to assign each object type to a distinct image region
- Example: "backpack" in left 50%, "pig" in right 50%
- Add buffer space (10-15% overlap) to prevent hard boundaries
- CRITICAL: Never let different object categories share the same conditioning region

### 2. Rewrite Prompt for Explicit Layout
Transform "N objects and M objects" into spatially explicit language:
- "four rabbits arranged in a row on the left, one sheep standing on the right"
- "six cars parked in two rows of three in the background, one kangaroo in the foreground center"
- "a red backpack sitting on the left side, a pink pig standing on the right side"

### 3. Apply Count-Specific Emphasis
For counts 4+:
- Use attention syntax: "(four rabbits:1.3)", "(exactly four:1.2)"
- Add negative prompt: "three rabbits, five rabbits, wrong number, merged animals"

### 4. Add Style Isolation
For heterogeneous objects (animal+object, vehicle+animal):
- Add to negative prompt: "hybrid, merged, fused, combined creature"
- Include material/texture anchors in positive prompt: "furry pig, leather backpack"

### 5. Increase Base Resolution
Counts 5+ or complex multi-type scenes need more latent capacity:
- Use 1024×1024 minimum for SDXL
- Use 1280×1280 for Flux

## Node Recipe (SDXL Example)
```
CLIPTextEncode (positive) -> ConditioningSetArea (object_type_1) -> ConditioningCombine
CLIPTextEncode (positive) -> ConditioningSetArea (object_type_2) -> ConditioningCombine
ConditioningCombine -> KSampler
```

## Validation
After generation, check:
- Correct count of each object type
- Visual separation between different object categories
- No hybrid/merged forms
- Each object retains its characteristic features