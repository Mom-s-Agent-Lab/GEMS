---
name: counting-objects
description: >-
  Enforce precise object counts (2-7 items) using regional conditioning nodes, explicit numerical layout prompts, and count-specific negative prompts to override diffusion model tendency to generate 1 or 3 items.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects

## Problem
Diffusion models have strong priors toward generating 1 or 3 objects regardless of prompt specification. Counts of 2, 4, 5, 6, 7+ fail without structural intervention.

## Solution Strategy
1. **Split the generation into regions** - one region per object using ConditioningSetArea or regional prompt nodes
2. **Explicit numerical enumeration** - list each object separately: "first cat, second cat, third cat, fourth cat"
3. **Negative prompt counts** - add "(single [object]:1.3), (one [object]:1.2), (three [object]:1.2)" to negative
4. **Layout specification** - add spatial arrangement: "arranged in a row", "in a circle", "grid of 2x3"

## Implementation

### For 2-3 objects:
- Prompt structure: "(exactly {count} {object}s:1.4), {ordinal list}, arranged in {layout}"
- Example: "(exactly two raccoons:1.4), first raccoon and second raccoon, side by side"
- Negative: "(single raccoon:1.3), (one raccoon:1.2), (three raccoons:1.2)"

### For 4-7 objects:
**MUST use regional conditioning:**
1. Divide canvas into N regions using ConditioningSetArea
2. Each region gets: CLIPTextEncode -> ConditioningSetArea with coordinates
3. Combine all regional conditionings with ConditioningCombine
4. Wire combined conditioning to KSampler positive slot

**Region division formula for count N:**
- Layout: grid arrangement (2×2 for 4, 2×3 for 6, etc.)
- Region width: image_width / columns
- Region height: image_height / rows
- Each ConditioningSetArea: (x, y, width, height, strength=1.0)

**Per-region prompt:**
- "single {object}, {unique_detail}, centered in frame"
- Example for "four rabbits": Region 1="single white rabbit, centered", Region 2="single gray rabbit, centered", etc.

### For mixed objects ("four rabbits and a sheep"):
1. Create N+1 regions (4 rabbit regions + 1 sheep region)
2. Assign larger region to primary object group
3. Add to global prompt: "exactly {count_a} {object_a}s and {count_b} {object_b}s"

## When to Use
- User specifies exact counts: "two", "four", "six", "seven"
- Verifier reports wrong object count
- Prompt contains "multiple", "several", "a pair of", "a group of N"
- Always trigger for counts ≥4

## Node sequence for 4+ objects:
```
CLIPTextEncode (obj1) -> ConditioningSetArea (region1) ->
CLIPTextEncode (obj2) -> ConditioningSetArea (region2) ->  ConditioningCombine ->
CLIPTextEncode (obj3) -> ConditioningSetArea (region3) ->  ConditioningCombine -> KSampler
CLIPTextEncode (obj4) -> ConditioningSetArea (region4) ->/
```