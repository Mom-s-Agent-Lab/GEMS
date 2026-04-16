---
name: counting-objects
description: >-
  Enforce precise object counts (4+) using per-instance regional prompts with spatial grid isolation, merger-prevention negatives, and attention re-weighting to ensure correct cardinality.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects (4+ instances)

## When to use
- User requests 4 or more instances of the same object type
- Verifier reports wrong object count, merged objects, or missing instances
- Prompt contains numerals ≥4 or words like "four", "five", "six", "seven", etc.
- Combine with unusual-attributes when objects have non-standard colors/materials

## Core strategy
1. **Spatial grid decomposition**: Divide image into N distinct regions (quadrants, rows, or circular positions)
2. **Per-instance regional prompts**: Create one regional prompt per object with explicit position tokens
3. **Merger prevention**: Add strong negative prompts: "conjoined, merged, fused, overlapping, touching, clustered"
4. **Attention boosting**: Use (object:1.3) or [object:1.2] per region to prevent dropout

## Node-level implementation

### Step 1: Query regional control capabilities
```python
regional_nodes = tool("search_nodes", query="regional prompt conditioning mask")
```

### Step 2: Construct base prompt with count enforcement
```
Base: "exactly {N} separate {object}s, each distinct and complete, evenly spaced, photographic clarity"
Negative: "merged objects, conjoined, fused, overlapping, fewer than {N}, more than {N}, clustered, touching"
```

### Step 3: Create N regional prompts (example for 5 bears)
```
Region 1 (top-left): "(single brown bear:1.3) in top left quadrant, isolated, complete"
Region 2 (top-right): "(single brown bear:1.3) in top right quadrant, isolated, complete"
Region 3 (center): "(single brown bear:1.3) in center, isolated, complete"
Region 4 (bottom-left): "(single brown bear:1.3) in bottom left, isolated, complete"
Region 5 (bottom-right): "(single brown bear:1.3) in bottom right, isolated, complete"
```

### Step 4: Apply masks with 10-15% overlap
- Use ConditioningSetMask or regional prompt nodes
- Ensure masks cover 100% of latent space collectively
- Allow small overlap to prevent gaps

### Step 5: Combine conditionings
- Use ConditioningCombine or ConditioningAverage
- Weight each region equally unless user specifies prominence

### Step 6: Sampler tuning for count accuracy
- **Steps**: 35-50 (more steps = better separation)
- **CFG**: 8.5-11.0 (higher CFG enforces regional boundaries)
- **Sampler**: dpmpp_2m or euler_ancestral (avoid LCM unless checkpoint requires it)
- If dreamshaper-lcm is active: read dreamshaper8-lcm skill first, use lcm sampler, steps=6-8, cfg=1.5-2.0

### Step 7: Verification loop
- After generation, check if count matches
- If objects are merged: increase CFG by 1.0, add "separated by space" to base prompt
- If objects are missing: increase steps by 10, boost attention weights to 1.4

## Common failures and fixes
- **Objects merge into blob**: Increase CFG, strengthen negative prompts, reduce mask overlap to 5%
- **Wrong count (N-1 objects)**: One region failed—increase attention weight for that position to 1.5
- **Unusual colors lost**: Run unusual-attributes skill first to get proper color/material tokens, then apply regional prompts
- **Multi-type scenes (e.g., "four rabbits AND a sheep")**: Create N+1 regions, last region for the different object type

## Output
Return modified workflow with regional conditioning nodes inserted before KSampler.