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
- User specifies exact counts: "three cats", "five apples", "two dogs and a pig"
- Multiple object types with different counts: "four rabbits and a sheep", "six cars and a kangaroo"
- Verifier reports wrong count, missing objects, or merged instances
- Count is 2 or higher (single objects don't need this)

## Critical Rules
1. **ALWAYS use regional-control** — text prompts alone cannot reliably enforce counts
2. **For mixed object types** (e.g., "a backpack and a pig"), treat EACH type as a separate counting task
3. **Combine with unusual-attributes** when colors/materials are non-standard ("green backpack")
4. **Spatial separation** prevents merging: assign each instance to a distinct grid cell or region

## Workflow Pattern

### Single Object Type (e.g., "five bears")
1. Create 5 regional prompt nodes, one per bear
2. Assign each to a distinct spatial region (grid layout: 2×3, 3×2, etc.)
3. Anchor with "exactly one bear", "single bear instance", "solo bear"
4. Use emphasis: "(bear:1.3)" in each region
5. Global negative: "multiple bears in one area, merged bears, duplicate"

### Multiple Object Types (e.g., "four rabbits and a sheep")
1. **Partition regions**: 4 regions for rabbits + 1 region for sheep
2. **Independent prompts**:
   - Rabbit regions: "exactly one rabbit, single rabbit, (rabbit:1.3), white fur"
   - Sheep region: "exactly one sheep, single sheep, (sheep:1.3), wool texture"
3. **Spatial layout**: place sheep in background/center, rabbits in foreground grid
4. **Isolation negative**: "rabbit with sheep features, sheep-rabbit hybrid, merged animals"
5. **Call regional-control** with these 5 separate conditioning zones

### Attribute Preservation (e.g., "a green backpack and a pig")
1. Region 1: "(green backpack:1.4), vibrant green color, bag, knapsack" + call unusual-attributes for green
2. Region 2: "(pig:1.3), pink skin, farm animal, solo pig"
3. Negative: "green pig, pink backpack, color contamination, merged objects"
4. Ensure regions don't overlap to prevent attribute bleed

## Node-Level Instructions
- Use `ConditioningSetArea` or `GLIGEN` for regional prompts
- Set `strength=1.0` and `width/height` to cover each instance's expected bbox
- For counts >5, use grid math: 6 items = 3×2 or 2×3 layout
- **Never** rely on "four" or "six" in the global prompt — diffusion models ignore count words

## Output
Return the updated workflow with regional conditioning applied. No prompt rewriting needed — regional-control handles it.