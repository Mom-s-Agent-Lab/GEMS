---
name: counting-objects
description: >-
  Enforce accurate object counts (2-7+) through sequential regional conditioning, explicit spatial positioning, count emphasis, and anti-fusion negative prompts.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects

## When to Use
Trigger when the user requests a specific number of objects (2-7+), especially:
- Explicit counts: "four rabbits", "seven croissants", "six cars"
- Multiple object types with counts: "four rabbits and a sheep"
- When verifier reports wrong count, missing objects, or fused/merged duplicates

## Core Problem
Diffusion models struggle with exact counts because:
1. Objects merge/fuse during generation
2. Count tokens are weakly attended
3. Spatial arrangements cause overlap
4. Higher counts (5+) exponentially increase failure rate

## Strategy

### 1. Sequential Regional Prompting
For counts ≥3, use ConditioningSetArea nodes to place each object in a separate spatial region:
- Divide the canvas into a grid (2×2 for 4 objects, 2×3 for 6, etc.)
- Assign each object instance to a distinct grid cell with x, y, width, height
- Use strength=1.0 for each region
- Combine all regions with ConditioningCombine before KSampler

Example for "four rabbits":
```
Region 1: "rabbit" at (0, 0, 512, 512)
Region 2: "rabbit" at (512, 0, 512, 512)
Region 3: "rabbit" at (0, 512, 512, 512)
Region 4: "rabbit" at (512, 512, 512, 512)
```

### 2. Explicit Enumeration in Prompt
Rewrite prompts to list each object individually:
- "seven green croissants" → "first green croissant, second green croissant, third green croissant, fourth green croissant, fifth green croissant, sixth green croissant, seventh green croissant"
- Add ordinal numbers to force distinct identity

### 3. Count Emphasis
Boost count tokens with CLIP emphasis:
- "(four:1.4) rabbits" or "((four)) rabbits"
- Place emphasis on the count word, not the object

### 4. Anti-Fusion Negative Prompt
Add to negative prompt:
"merged objects, fused, conjoined, blurred together, overlapping, duplicate, copy-paste, single object, fewer than [N], more than [N]"

### 5. High CFG + High Steps
- CFG scale: 8.5-10.0 (higher adherence to prompt structure)
- Steps: 35-50 (more sampling gives count constraint time to stabilize)

### 6. Multi-Type Counting
For "four rabbits and a sheep":
- Create 5 regional areas (4 for rabbits, 1 for sheep)
- Keep sheep region larger and central to establish it as distinct
- Use negative prompt: "rabbit with wool, sheep with long ears, hybrid animal"

## Implementation Checklist
- [ ] Detect count ≥2 in prompt
- [ ] Create ConditioningSetArea nodes (one per object instance)
- [ ] Position regions in non-overlapping grid
- [ ] Add ordinal enumeration to prompt text
- [ ] Emphasize count token: (count:1.4)
- [ ] Inject anti-fusion negative prompt
- [ ] Set CFG=8.5+, steps=35+
- [ ] Combine all regions before sampler

## Failure Recovery
If count is still wrong:
- Increase region separation (add 10% padding between cells)
- Raise count emphasis to (count:1.6)
- Add "arranged in a grid" or "spaced apart" to prompt
- Try ControlNet depth/canny with a reference layout image