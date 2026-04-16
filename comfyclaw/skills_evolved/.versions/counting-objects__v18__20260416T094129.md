---
name: counting-objects
description: >-
  Enforce precise object counts (especially 6-7+) using per-instance regional prompts with spatial grid decomposition, attention weighting, and iterative conditioning to prevent merging.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects (6-7+ instances)

## When to use
- User requests specific counts: "six cars", "seven croissants", "four apples and three oranges"
- Verifier reports wrong object count or merged instances
- fix_strategy contains "fix_object_count" or "prevent_merging"

## Critical for counts ≥6
Standard regional prompting fails at 6-7 objects because:
- Attention maps blur together
- Model defaults to "several" or "many" instead of exact count
- Objects merge into amorphous groups

## Implementation strategy

### 1. Spatial grid decomposition
- Divide canvas into explicit grid: 3×2 for 6 objects, 3×3 for 7-9
- Assign each object to a distinct cell
- Calculate regional masks with 10-15% overlap buffer
- Use SetNode to create mask coordinates: x_start, y_start, width, height

### 2. Per-instance conditioning
```
For "seven green croissants":
- Regional prompt 1 (cell 0,0): "a single green croissant, (isolated:1.3)"
- Regional prompt 2 (cell 0,1): "a single green croissant, (isolated:1.3)"
- ...
- Regional prompt 7 (cell 2,1): "a single green croissant, (isolated:1.3)"
- Base prompt: "(exactly seven:1.4) green croissants, evenly spaced, (distinct separate objects:1.3)"
```

### 3. Attention weighting per region
- Apply ConditioningSetMask to each regional CLIPTextEncode output
- Set strength=1.2 for each region to prevent bleed
- Use ConditioningCombine to merge all regional conditions
- Final combined conditioning → KSampler

### 4. Negative prompt reinforcement
```
"merged objects, clustered, grouped, overlapping, blurry count, (approximate number:1.2), multiple objects in one, fused, combined"
```

### 5. Sampler tuning for cardinality
- steps: 35-45 (higher for 7+)
- cfg_scale: 8.5-10.0 (stronger guidance)
- sampler: dpmpp_2m or euler_ancestral
- Use LatentUpscale at 1.5x before KSampler if base resolution <1024px

## Node sequence
1. Calculate grid layout based on count
2. Create regional masks (ConditioningSetArea or custom mask nodes)
3. CLIPTextEncode for each cell with "(single:1.3) [object]" + isolation emphasis
4. ConditioningSetMask for each region
5. ConditioningCombine all regions sequentially
6. Add base prompt with "(exactly N:1.4)" emphasis
7. ConditioningCombine base + regional
8. Pass to KSampler with cfg=9.0, steps=40

## Verification
- Count instances in verifier feedback
- If count still wrong: increase regional mask overlap to 20%, boost cfg to 11.0, add "(separate individual:1.5)" to each region
- If objects merge: reduce mask overlap, increase isolation emphasis to 1.5