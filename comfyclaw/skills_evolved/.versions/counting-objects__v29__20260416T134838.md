---
name: counting-objects
description: >-
  Enforce accurate object counts (2-10+) through mandatory regional-control with multi-row grid layouts, escalating attention emphasis (1.3-1.8 based on count), and per-instance position tokens. MUST combine with unusual-attributes for non-standard colors/materials.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

## When to Use
Trigger when the user requests a specific count of 2 or more identical or similar objects (e.g., "five cats", "seven croissants", "six cars").

## Core Strategy
Diffusion models collapse multiple objects into fewer instances without explicit spatial separation and per-instance emphasis.

## Implementation Steps

### 1. Count-Based Grid Layout
**Counts 2-3:** Single row, left-to-right
- Position tokens: `on the left`, `in the center`, `on the right`

**Counts 4-6:** 2×3 grid (2 rows, 3 columns)
- Row 1: `top-left`, `top-center`, `top-right`
- Row 2: `bottom-left`, `bottom-center`, `bottom-right`

**Counts 7-9:** 3×3 grid
- Add middle row: `middle-left`, `middle-center`, `middle-right`

**Counts 10+:** Cluster layout
- Use `arranged in a grid`, `scattered across the scene`, `lined up in rows`

### 2. Regional Control Integration
MUST use regional-control skill with these parameters:
- **One region per object instance**
- **Region masks:** Non-overlapping grid cells covering 80-90% of canvas
- **Prompt per region:** `[object description] positioned at [position token], (solo:1.4)`

### 3. Emphasis Scaling
Increase emphasis based on count:
- 2-3 objects: `(object:1.2)` per region
- 4-6 objects: `(object:1.4)` per region
- 7+ objects: `(object:1.6)` per region, add `(exactly [N] objects:1.5)` to base prompt

### 4. Unusual Attributes Combination
If objects have non-standard colors/materials (e.g., "green croissants", "purple dogs"):
- Apply unusual-attributes skill FIRST to get attribute-enforced prompt structure
- Then wrap each regional prompt with the attribute emphasis
- Example: `(green croissant:1.6) positioned at top-left, (green pastry:1.3), (solo:1.4)`

### 5. Negative Prompt
Add to base negative prompt:
- For counts 5+: `merged objects, fused items, single object, combined, overlapping`
- For counts 7+: `pile, cluster, group, crowd` (prevents collapse into amorphous mass)

### 6. Verification
After generation, if count is still wrong:
- Increase emphasis by +0.2 per region
- Reduce region overlap (increase margins between masks)
- Add `multiple distinct [objects]` to base prompt
- Consider splitting into two passes: generate N/2 objects twice and composite

## Example: "Seven Green Croissants"
1. Detect count=7, unusual color=green → trigger unusual-attributes + counting-objects
2. Use 3×3 grid (7 filled cells)
3. Base prompt: `(exactly seven objects:1.5), multiple distinct croissants arranged in a grid`
4. Regional prompts (7 regions):
   - Region 1: `(green croissant:1.6) positioned at top-left, (vibrant green pastry:1.4), (solo:1.4)`
   - Region 2: `(green croissant:1.6) positioned at top-center, (vibrant green pastry:1.4), (solo:1.4)`
   - ... (repeat for all 7 positions)
5. Negative: `brown croissant, golden pastry, merged objects, fused items, pile, cluster`
6. Apply regional-control with 7 non-overlapping masks in 3×3 grid pattern