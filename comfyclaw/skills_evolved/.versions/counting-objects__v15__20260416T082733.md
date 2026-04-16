---
name: counting-objects
description: >-
  Enforce precise object counts using tiered strategies: count tokens for 1-2 objects, spatial grid + regional prompts for 3-4 objects, and multi-tile regional decomposition with explicit positioning for 5+ objects.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects

Diffusion models struggle with counts beyond 2-3 objects. Use tiered strategies:

## Strategy Selection
- **1-2 objects**: Count-specific tokens ("one cat", "two dogs")
- **3-4 objects**: Spatial grid layout + regional-control skill
- **5+ objects**: Multi-tile regional decomposition (see below)

## For 5+ Objects (HIGH COUNT)

**Critical**: Standard regional prompting fails beyond 4 objects. Use this expanded strategy:

1. **Divide canvas into N zones** matching object count
   - For 5 objects: create 5 distinct regional mask zones
   - For 6-7 objects: use 2 rows × 3-4 columns grid
   - For 8+ objects: use 3×3 or 4×3 grid

2. **Create one ConditioningSetMask per object**
   - Each mask covers exactly 1/N of the canvas
   - No overlap between masks
   - Example for 5 objects horizontally: masks at (0.0-0.2), (0.2-0.4), (0.4-0.6), (0.6-0.8), (0.8-1.0)

3. **Anchor each object with spatial tokens**
   - Prompt format: "on the far left", "second from left", "in the center", "second from right", "on the far right"
   - For vertical grids: "top row left", "top row center", etc.

4. **Use ConditioningCombine to merge all regions**
   - Chain combine nodes: obj1+obj2 -> temp1, temp1+obj3 -> temp2, etc.

5. **Add global background conditioning**
   - Create a weak (strength 0.3-0.5) full-canvas conditioning for environment
   - Combine last with ConditioningAverage to blend with object regions

6. **Boost sampler steps**
   - Use steps=35-50 for 5-7 objects (up from default 20-30)
   - CFG 7.5-9.0 to strengthen adherence

## Example Node Sequence (6 objects)
```
CLIPTextEncode ("purple truck, on the far left") -> ConditioningSetMask (x=0.0-0.166) -> cond1
CLIPTextEncode ("purple truck, left of center") -> ConditioningSetMask (x=0.166-0.333) -> cond2
CLIPTextEncode ("purple truck, slightly left") -> ConditioningSetMask (x=0.333-0.5) -> cond3
CLIPTextEncode ("purple truck, slightly right") -> ConditioningSetMask (x=0.5-0.666) -> cond4
CLIPTextEncode ("purple truck, right of center") -> ConditioningSetMask (x=0.666-0.833) -> cond5
CLIPTextEncode ("purple truck, on the far right") -> ConditioningSetMask (x=0.833-1.0) -> cond6

ConditioningCombine(cond1, cond2) -> temp1
ConditioningCombine(temp1, cond3) -> temp2
ConditioningCombine(temp2, cond4) -> temp3
ConditioningCombine(temp3, cond5) -> temp4
ConditioningCombine(temp4, cond6) -> final_positive
```

## When to Trigger
- User requests 5 or more of the same object type
- Prompts like "seven X", "six Y and a Z" (where Y count ≥5)
- Verifier reports missing objects in high-count scenarios
- fix_strategy contains "increase_regional_granularity"

## Compatibility
- Always pair with unusual-attributes if objects have non-standard colors/materials
- Can combine with spatial skill for mixed-count scenes
- Increase resolution to 1024×768 or 768×1024 to give objects space