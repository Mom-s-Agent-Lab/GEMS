---
name: counting-objects
description: >-
  Enforce accurate object counts (2-10+) through regional conditioning with scaled canvas division for high counts (5+), per-object regional prompts, spatial positioning, attention emphasis, and fusion-prevention techniques. MUST combine with unusual-attributes skill when objects have non-standard colors or materials.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

## Trigger Conditions
- User specifies exact counts: "three cats", "five bears", "seven croissants", "six cars"
- Counts range from 2 to 10+ objects of the same type
- When verifier reports wrong object count or merged/fused objects

## Core Strategy

For counts 2-4: Use standard regional conditioning with horizontal/grid splits.

For counts 5+: MANDATORY high-count protocol:
1. **Canvas Division**: Split canvas into N equal regions (horizontal strip for 5-6, 2x3 grid for 6, 2x4 for 7-8)
2. **Per-Object Regional Prompts**: Create one regional prompt per object, each locked to its own canvas region
3. **Explicit Positioning**: Add position tokens to each regional prompt ("leftmost", "second from left", "top-left", "center-right")
4. **Index Labeling**: Number each object in its regional prompt ("first bear", "second bear", "third bear")
5. **Fusion Prevention**: Add negative prompt for each region: "merged, combined, fused, overlapping, duplicate"
6. **Count Reinforcement**: In base prompt, use repetition: "five bears, exactly 5 bears, bear bear bear bear bear"

## Node-Level Implementation

```
# For 5+ objects:
ConditioningSetArea (per object):
  - width: canvas_width / columns
  - height: canvas_height / rows  
  - x: region_index * region_width
  - y: row_index * region_height
  - strength: 1.8-2.0 (higher for counts 7+)

ConditioningCombine:
  - Chain all regional conditions sequentially
  - Final combine with base prompt at strength 1.0

Prompt structure per region:
  "[position token] [index] [object] [attributes], isolated, separated, distinct"
  Example: "top-left first green croissant, isolated, separated"

Base prompt:
  "[count as word] [count as digit] [object], [attributes], arranged in grid, spaced apart, NOT merged, NOT overlapping"
  Example: "seven 7 green croissants, arranged in grid, spaced apart, NOT merged"

Negative prompt (global):
  "fused objects, merged, combined, overlapping, duplicate, [count-1] [object], [count+1] [object]"
  Example for 5: "fused bears, merged, combined, overlapping, duplicate, 4 bears, 6 bears"
```

## Attribute Coordination

When unusual-attributes skill is active:
- Apply color/material tokens in EACH regional prompt
- Add material reinforcement in negative prompt: "NOT [default color] [object]"
- Example: "green croissant" + negative "NOT brown croissant, NOT golden croissant"

## Validation

Before executing:
- Verify region count matches object count
- Ensure no region overlap
- Check that combined strength * region_count < 12 (prevents oversaturation)

After generation:
- If count is wrong, increase regional strength by 0.2
- If objects are fused, reduce region size by 10% and add spacing tokens