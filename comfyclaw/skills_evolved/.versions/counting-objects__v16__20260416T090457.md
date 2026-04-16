---
name: counting-objects
description: >-
  Enforce precise object counts using regional prompts with explicit per-instance conditioning, attention weighting, and spatial grid decomposition to prevent merging and ensure correct cardinality.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects

## Trigger Conditions
- User specifies exact counts: "three cats", "five apples", "seven croissants"
- Prompts with numerical determiners: "four rabbits and a sheep"
- When verifier reports wrong object count or missing instances

## Strategy by Count

### 1-2 Objects
- Use attention weighting: `(subject:1.3)` for each instance
- Add count token explicitly: `two distinct cats, 2 cats`
- Negative prompt: `single cat, one cat, merged, conjoined`

### 3-4 Objects
**REQUIRED: Regional prompts with spatial grid**
1. Divide canvas into explicit regions (2x2 grid for 4, triangular for 3)
2. Use RegionalPromptSimple or ConditioningSetMask for EACH object
3. Allocate non-overlapping mask regions with feathering at most 10px
4. Per-region prompt: `(single {object}:1.4), one {object}, isolated`
5. Global negative: `multiple in one spot, merged, crowd, group, duplicate`
6. Base prompt after regional: `exactly {count} {objects}, {count} distinct {objects}`

### 5-7 Objects
**REQUIRED: Multi-tile regional decomposition**
1. Use RegionalPromptSimple with 6-8 non-overlapping masks
2. Assign each object to explicit (x,y) position in prompt:
   - `top-left corner: (one green croissant:1.5)`
   - `center-right: (one green croissant:1.5)`
3. Create conditioning mask per object at 128x128 minimum size
4. Apply ConditioningCombine sequentially, not in parallel
5. Final global conditioning: `scene with exactly {count} {objects}, total count {count}, {count} individual items`
6. Negative prompt: `fewer than {count}, more than {count}, merged objects, overlapping, crowd`
7. Increase steps to 35+ and CFG to 8.5 for stronger adherence

### Multi-Type Scenes (e.g., "four rabbits and a sheep")
1. Apply regional strategy for TOTAL object count
2. Allocate masks per animal type proportionally
3. Per-region prompts must include type AND singularity:
   - Region 1-4: `(single rabbit:1.5), one rabbit, isolated rabbit`
   - Region 5: `(single sheep:1.5), one sheep, isolated sheep`
4. Global prompt: `four rabbits and one sheep, 4 rabbits, 1 sheep, five animals total`
5. Negative: `extra animals, wrong count, merged animals, rabbit-sheep hybrid`

## Critical Rules
- **Always** use regional prompts for 3+ objects — count tokens alone fail
- Non-overlapping masks prevent merging; feathering must be minimal
- Explicit position language (top-left, bottom-right) reduces ambiguity
- Higher CFG (8-9) increases prompt adherence for counting tasks
- Test mask coverage: total area should be 60-80% of canvas, not 100%

## Node Implementation
```
For 3+ objects:
1. Create base conditioning from main prompt
2. For each object i in 1..count:
   - Create mask at position grid[i]
   - ConditioningSetMask(base_cond, mask, strength=0.9, set_cond_area="default")
3. ConditioningCombine all masked conditions
4. Append global count conditioning via ConditioningConcat
```

## Validation
- After generation, check object count in output
- If count < target: increase per-object attention to 1.6, reduce mask overlap
- If count > target: strengthen negative prompt, reduce mask feathering
- If objects merge: decrease mask size, increase inter-mask distance