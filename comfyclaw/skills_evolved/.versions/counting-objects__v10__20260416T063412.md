---
name: counting-objects
description: >-
  Enforce precise object counts (2-7 items) using iterative regional masking, per-object conditioning zones with count isolation, numerical layout tokens, and progressive negative prompts that explicitly reject incorrect counts.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects (2-7 items)

## Detection
Trigger when:
- User specifies exact counts: "four rabbits", "six cars", "three zebras"
- Multiple object types with quantities: "four rabbits and a sheep"
- Count >= 2 and <= 7 for any single object type

## Core Strategy
Diffusion models collapse counts above 3 without explicit spatial partitioning. For counts >= 4, use granular regional masking.

## Implementation

### For counts 4-7 (high-count mode):
1. **Spatial Grid Layout**: Divide the canvas into N equal regions using RegionalPromptSimple or ConditioningSetMask
   - 4 items: 2x2 grid
   - 5-6 items: 2x3 grid
   - 7 items: circular or 3x3 grid with center empty

2. **One Region Per Object**: Create separate conditioning for EACH instance
   - Region 1: "single [object], isolated, lone [object], only one"
   - Region 2: "single [object], isolated, lone [object], only one"
   - Continue for all N regions
   - **Critical**: Use "single" and "only one" in EACH region to prevent count bleeding

3. **Count-Specific Negatives**: Add to negative prompt:
   - "crowd, group, herd, flock, multiple [objects] together, [wrong_count] [objects]"
   - For "four rabbits": negative = "five rabbits, three rabbits, two rabbits, six rabbits"

4. **Background Isolation**: Add final region covering gaps between objects:
   - Prompt: "empty space, clean background, separation"
   - Prevents objects from merging

### For counts 2-3 (standard mode):
1. Use regional conditioning with 50/50 or 33/33/33 split
2. Each region: "a [object], single [object]"
3. Negative: "group of [objects], multiple [objects] together"

### Multi-Type Scenes:
"four rabbits and a sheep":
1. Allocate 4 regions for rabbits (2x2 grid in left 70% of canvas)
2. Allocate 1 region for sheep (right 30%)
3. Each rabbit region: "single rabbit, one rabbit, isolated"
4. Sheep region: "single sheep, one sheep"
5. Negative: "five rabbits, three rabbits, two sheep, multiple sheep"

## Parameters
- CFG: 8.5-10 (higher guidance enforces regional boundaries)
- Steps: 35-45 (more steps = better region separation)
- If using Flux/SDXL: use regional_prompting_simple or multiple ControlNets with segmentation masks

## Node Pattern
```
For each object instance i:
  ConditioningSetMask(
    conditioning=CLIPTextEncode("single [object], isolated, only one"),
    mask=create_grid_mask(position=i, total=count)
  )
Combine all with ConditioningCombine in sequence
```

## Verification
After generation, if verifier reports wrong count:
- Increase region separation (add 10-20px gaps)
- Boost negative prompt weight: "(crowd:1.3), (herd:1.3)"
- Reduce step count overlap by using different seeds per region if supported