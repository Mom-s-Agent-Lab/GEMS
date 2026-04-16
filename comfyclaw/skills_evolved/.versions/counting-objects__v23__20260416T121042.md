---
name: counting-objects
description: >-
  Enforce accurate object counts (2-7+) in single-type AND mixed-type scenes through per-object-type regional conditioning, explicit spatial positioning, count emphasis, and anti-fusion negative prompts.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

## When to Use
Trigger when the prompt contains:
- Explicit counts: "three cats", "five trees", "seven balloons"
- Multiple objects of SAME type: "rabbits in a field" (plural)
- Multiple objects of DIFFERENT types: "four rabbits and a sheep", "six cars and a kangaroo"
- Counts above 2 (diffusion models handle 1-2 objects naturally)

## Mixed-Object Strategy (CRITICAL)
When the prompt contains TWO OR MORE object types (e.g., "four rabbits and a sheep"):

1. **Parse object types separately**:
   - Extract each object type and its count
   - Example: "four rabbits and a sheep" → [("rabbit", 4), ("sheep", 1)]

2. **Create independent regional prompts per object type**:
   - Use ConditioningSetArea or regional prompt nodes
   - Assign NON-OVERLAPPING spatial zones to each object type
   - Example: rabbits in left 70% of canvas, sheep in right 30%

3. **Apply count emphasis PER object type**:
   - For each region: "(exactly N [object]:1.4), N distinct [object]s, (N separate [object]s:1.3)"
   - Example rabbit region: "(exactly 4 rabbits:1.4), 4 distinct rabbits, (4 separate rabbits:1.3)"
   - Example sheep region: "(exactly 1 sheep:1.4), 1 distinct sheep, (1 separate sheep:1.3)"

4. **Combine with ConditioningCombine**:
   - Wire all regional conditions through ConditioningCombine
   - Preserve individual object identity

## Single-Object-Type Strategy
When all objects are the same type:

1. **Spatial distribution**:
   - Add explicit positioning: "arranged in a row", "scattered across the scene", "in a cluster"
   - For 4+ objects: "spread out, well-separated"

2. **Count emphasis in main prompt**:
   - "(exactly N [object]s:1.4), N distinct [object]s visible, (N separate [object]s:1.3)"
   - Repeat the number in words AND digits

3. **Anti-fusion negative prompt**:
   - "merged [object]s, fused [object]s, conjoined [object]s, blended [object]s, single [object], overlapping [object]s"

## Sampler Tuning
- CFG: 8.5-10 (higher guidance for count accuracy)
- Steps: 35+ (more steps = better count adherence)
- Sampler: dpmpp_2m or euler_ancestral (deterministic samplers work better)

## Verification
After generation, check:
- Each object type appears with correct count
- Objects are visually distinct (not merged/fused)
- Mixed scenes maintain clear boundaries between object types