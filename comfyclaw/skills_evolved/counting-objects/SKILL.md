---
name: counting-objects
description: >-
  Enforce accurate object counts (2-10+) through mandatory regional prompting with explicit per-object spatial grid allocation, individual conditioning per instance, and count-verification negative prompts.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

## When to Use
Trigger when the prompt contains explicit counts of 2 or more identical/similar objects:
- "three cats", "four rabbits", "seven croissants", "six trucks"
- ANY numeric word (two, three, four, five, six, seven, eight, nine, ten) + plural noun
- "multiple", "several", "many" + specific object type

## Core Strategy
Diffusion models collapse multiple identical objects into fewer instances. Combat this through:
1. **Spatial grid allocation**: Divide canvas into N regions (2×2 for 4, 2×3 for 6, 3×3 for 9)
2. **Per-instance regional conditioning**: Each region gets ONE object with explicit position
3. **Count-verification negatives**: Actively suppress wrong counts

## Implementation (4+ objects - MANDATORY)

### Step 1: Calculate Grid Layout
- 2-3 objects: horizontal or triangular layout
- 4 objects: 2×2 grid
- 5-6 objects: 2×3 grid  
- 7-9 objects: 3×3 grid
- 10+ objects: 4×3 or larger

### Step 2: Regional Prompting Setup
Use `RegionalPromptSimple` or `RegionalConditioningSimple` nodes:
```
For "four brown monkeys":
- Region 1 (top-left): "one brown monkey, left side, upper area"
- Region 2 (top-right): "one brown monkey, right side, upper area" 
- Region 3 (bottom-left): "one brown monkey, left side, lower area"
- Region 4 (bottom-right): "one brown monkey, right side, lower area"
```

### Step 3: Base Prompt Structure
Main prompt: "exactly {N} {objects}, {N} individual {objects}, full scene, all visible, arranged in grid"

Negative prompt: "fewer than {N}, only {N-1}, merged {objects}, overlapping {objects}, duplicate, missing {objects}"

### Step 4: Per-Region Emphasis
Each regional prompt:
- Uses "one {object}" or "single {object}" (never plural)
- Includes spatial anchor ("left side", "center", "right side", "top", "bottom")
- Adds "clearly visible, distinct, separate"
- Regional strength: 0.8-1.0

### Step 5: Verification Tokens
Add to main positive prompt:
- "count of {N}"
- "{N} distinct {objects}"
- "no more, no less"

## Special Cases

**Unusual attributes (green croissants, purple trucks):**
Bind attribute to EACH regional prompt:
- Region 1: "one green croissant, left side"
- Region 2: "one green croissant, center"
- etc.

**Small objects (< 6):** Use simpler layout (row/triangle) but still enforce per-instance regions

**7+ objects:** ALWAYS use 3×3 or larger grid. Consider increasing resolution to 1024×1024 minimum.

## Node Wiring
1. `CLIPTextEncode` → base positive
2. `CLIPTextEncode` → base negative  
3. For each region: `RegionalPromptSimple` with mask + per-instance prompt
4. `ConditioningCombine` to merge all regional conditions
5. Feed combined conditioning to `KSampler`

## Critical Parameters
- CFG: 7-9 (higher CFG helps maintain count)
- Steps: 35-50 (more steps = better separation)
- Sampler: dpmpp_2m or euler_a
- Regional mask feather: 0.1-0.2 (minimize bleed)

## Fallback
If regional nodes unavailable: Restructure prompt with explicit enumeration:
"first {object} on the left, second {object} in the center-left, third {object} in the center-right, fourth {object} on the right"