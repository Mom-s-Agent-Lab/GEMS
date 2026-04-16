---
name: counting-objects
description: >-
  Enforce accurate object counts (2-10+) through regional prompting with explicit per-object conditioning, spatial grid layouts, and count-verification negative prompts.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

## When to Use
Trigger when the prompt specifies an exact count of 2 or more objects ("three cats", "four rabbits", "five trees", "two dogs and three birds"). Even when regional-control is already active, this skill adds count-specific enforcement.

## Core Strategy
Diffusion models struggle with exact counts because attention disperses across tokens. Solution: create one regional prompt per object instance with spatial isolation.

## Implementation Steps

### 1. Spatial Grid Layout (Critical for 3-4 counts)
For N objects, divide the canvas into N non-overlapping regions:
- 2 objects: left half (0.0-0.5) | right half (0.5-1.0)
- 3 objects: left third (0.0-0.33) | center (0.33-0.67) | right (0.67-1.0)
- 4 objects: 2×2 grid → top-left (0.0-0.5, 0.0-0.5), top-right (0.5-1.0, 0.0-0.5), bottom-left (0.0-0.5, 0.5-1.0), bottom-right (0.5-1.0, 0.5-1.0)
- 5+ objects: arrange in rows, ensure 0.15+ spacing between regions

### 2. Regional Prompt Construction
For "four purple lions":
```
Region 1 (0.0-0.5, 0.0-0.5): "one purple lion, single lion, solo"
Region 2 (0.5-1.0, 0.0-0.5): "one purple lion, single lion, solo"
Region 3 (0.0-0.5, 0.5-1.0): "one purple lion, single lion, solo"
Region 4 (0.5-1.0, 0.5-1.0): "one purple lion, single lion, solo"
```

### 3. Emphasis Syntax (Boost for 3-4 counts)
Add emphasis to singular tokens:
- "(one:1.3) purple lion, (single:1.2) lion, (solo:1.2)"
- For 3-4 objects, use emphasis 1.3-1.4 on count words

### 4. Count-Verification Negative Prompt
Add to global negative: "multiple [object]s in one area, [N+1] [object]s, [N-1] [object]s, merged [object]s, overlapping [object]s, crowd of [object]s"

For "four rabbits": negative += "five rabbits, three rabbits, two rabbits, multiple rabbits in one spot, rabbit crowd, merged rabbits"

### 5. Regional Isolation (Prevent Bleed)
Set regional prompt strength to 0.9-1.0 for count tasks. Use ConditioningSetMask or RegionalPromptSimple nodes with feather=0.05 (tight boundaries).

### 6. Verification
After generation, if count is wrong:
- Increase region spacing by 0.1
- Add "exactly [N] [object]s" to global positive
- Increase emphasis to 1.5 on "one" and "single"
- Add "(counting error:1.4)" to negative prompt

## Node Sequence
1. Calculate grid coordinates for N objects
2. Create N regional conditioning nodes, one per object
3. Each regional node: singular prompt + tight mask
4. Combine all regions with ConditioningCombine
5. Add count-verification negative globally
6. Feed to sampler

## Common Failures
- Objects merge → increase region spacing to 0.2+
- Missing objects → verify each region has explicit "one [object]" token
- Wrong count → add "[wrong_count] [object]s" to negative for each incorrect count near target