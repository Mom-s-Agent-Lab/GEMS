---
name: counting-objects
description: >-
  Enforce accurate object counts (2-10+) through multi-stage validation: regional prompting with per-instance anchoring, spatial grid layouts for 4+ objects, iterative count verification, and fallback to ControlNet tile grids when counts exceed 6.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

## When to Use
Trigger when the prompt specifies an exact count of objects ("three cats", "five chairs", "seven croissants") or compound counts ("four rabbits and a sheep"). Also trigger when verifier reports wrong object count or missing instances.

## Critical Threshold Rules
- **2-3 objects**: Regional prompting with spatial anchors ("left", "center", "right")
- **4-6 objects**: MUST use spatial grid layout ("top-left", "top-right", "center-left", etc.) + per-instance emphasis
- **7+ objects**: Grid layout + consider ControlNet tile/segmentation OR iterative generation with inpainting

## Implementation Strategy

### Step 1: Count Detection
Parse the prompt for:
- Explicit numerals: "four", "seven", "4", "7"
- Compound patterns: "N [type1] and M [type2]"
- Extract total_count and per_type_counts

### Step 2: Spatial Layout (4+ objects)
For counts ≥4, create explicit spatial grid:
```
[object1] in top-left corner, [object2] in top-right corner,
[object3] in center-left, [object4] in center-right,
[object5] in bottom-left, [object6] in bottom-right
```

### Step 3: Regional Prompting
Use `ConditioningSetArea` nodes (one per instance) with:
- **width/height**: 0.4-0.5 (40-50% of image, allows overlap)
- **x/y**: Grid positions calculated from layout
- **strength**: 0.8-1.0 for counts >4
- Each region gets: "(single [object_type]:1.3), [attributes], isolated"

### Step 4: Numerical Anchoring
In base prompt, add:
- "exactly [N] [objects], [N] total, complete set of [N]"
- Negative: "extra objects, duplicate, merged, fewer than [N]"

### Step 5: Per-Instance Emphasis (4+ objects)
For each instance in regional prompt:
```
"(one single [object]:1.4), individual [object], separate distinct [object]"
```

### Step 6: Fallback for 7+ Objects
If count ≥7 and regional-control available:
- Consider recommending ControlNet with tile/segmentation preprocessor
- OR suggest breaking into 2 generations + compositing
- Warn user that diffusion models struggle with >6 distinct instances

## Node Configuration
- **CFG scale**: 8-10 (higher guidance for count accuracy)
- **Steps**: 35-40 (more steps = better instance separation)
- **Sampler**: dpmpp_2m or euler_a (deterministic)

## Example: "seven green croissants"
Base prompt:
```
"exactly seven green croissants, 7 total croissants, complete set of 7,
(seven:1.3) vibrant green pastries arranged in grid"
```
Negative:
```
"extra croissants, duplicate, merged, fewer than 7, brown croissants"
```
Regional layout (7 instances):
- R1: top-left (x=0.1, y=0.1, w=0.35, h=0.35) -> "(one single green croissant:1.4)"
- R2: top-center (x=0.35, y=0.1, w=0.3, h=0.35) -> "(one single green croissant:1.4)"
- R3: top-right (x=0.65, y=0.1, w=0.35, h=0.35) -> "(one single green croissant:1.4)"
- R4: center-left (x=0.15, y=0.4, w=0.3, h=0.3) -> "(one single green croissant:1.4)"
- R5: center (x=0.4, y=0.4, w=0.2, h=0.3) -> "(one single green croissant:1.4)"
- R6: center-right (x=0.6, y=0.4, w=0.3, h=0.3) -> "(one single green croissant:1.4)"
- R7: bottom-center (x=0.35, y=0.7, w=0.3, h=0.3) -> "(one single green croissant:1.4)"

## Compound Counts ("four rabbits and a sheep")
- Total instances: 5
- Use 4+ strategy with grid layout
- Each rabbit region: "(one single rabbit:1.4), individual rabbit"
- Sheep region: "(one single sheep:1.4), individual sheep, distinct from rabbits"
- Base prompt: "exactly four rabbits and one sheep, 5 total animals, 4 rabbits plus 1 sheep"

## Success Criteria
- Every instance appears as separate entity
- Total count matches request
- No merged/duplicate instances
- Attributes preserved per instance