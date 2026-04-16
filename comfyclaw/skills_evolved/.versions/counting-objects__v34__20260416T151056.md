---
name: counting-objects
description: >-
  Enforce accurate object counts (2-7+) for single OR multiple object types through regional-control, numerical anchoring, spatial grids, and per-instance emphasis. MUST handle heterogeneous objects independently.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects

## When to Use
Trigger when the user specifies an exact count of objects ("three cats", "five apples", "six cars and a kangaroo", "seven black cows"). Essential for counts ≥2.

## Core Strategy

### For counts 2-4:
- Use regional-control with explicit spatial grid: "left", "right", "center", "top-left", etc.
- Add numerical anchoring: "exactly N", "N individual", "group of N"
- Per-instance emphasis: (object:1.2) repeated N times in different regions

### For counts 5-7+ (HIGH PRIORITY):
- **MUST use explicit grid layout**: "arranged in a grid", "in two rows", "in a circle", "spread across the scene"
- **Stronger numerical emphasis**: "exactly N", "precisely N separate", "N distinct individual"
- **Increase regional subdivision**: For 6 objects use 3×2 grid; for 7 use 3+2+2 or circular arrangement
- **Boost per-instance conditioning**: Use (object:1.3) or (object:1.4) for each instance
- **Add negative prompt**: "fewer than N", "less than N", "merged", "combined"
- **Increase sampler steps by +5-10** for counts ≥6 to allow model convergence

### For heterogeneous counts ("six cars and a kangaroo"):
- Apply regional-control with SEPARATE regions for each object type
- Anchor each type independently: "exactly 6 cars" + "exactly 1 kangaroo"
- Never merge object types in the same regional prompt

## Example Transforms

**Input**: "seven black cows"
**Output**: "exactly 7 distinct individual black cows arranged in a grid, (black cow:1.4), (black cow:1.4), (black cow:1.4), (black cow:1.4), (black cow:1.4), (black cow:1.4), (black cow:1.4), 7 separate animals"
**Negative**: "fewer than 7, less than 7, merged cows, 6 cows, combined"
**Steps**: base_steps + 8

**Input**: "six cars and a kangaroo"
**Output**: Regional prompt 1 (80% coverage): "exactly 6 distinct cars in two rows, (car:1.3) repeated 6 times"
Regional prompt 2 (20% coverage): "exactly 1 kangaroo, single marsupial"
**Steps**: base_steps + 6

## Node-Level Implementation
- Use regional-control skill to create ConditioningSetArea nodes
- For counts ≥6: set area_width/area_height to create non-overlapping grid cells
- Increase KSampler steps parameter when count ≥6
- Apply ConditioningCombine to merge all regional conditions