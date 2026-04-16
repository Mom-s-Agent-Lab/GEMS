---
name: counting-objects
description: >-
  Enforce accurate object counts (2-7+) for single OR compound heterogeneous scenes through regional-control, numerical anchoring, spatial grids, and per-instance emphasis. MUST handle asymmetric counts (N+1 patterns).
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects

## When to Use
Trigger when the user specifies an exact count of objects (2-7+), including:
- Single type: "five cats", "seven cars"
- Compound scenes: "six cars and a kangaroo", "five bears and a donut", "a trumpet and three sheeps"
- Multiple types with counts: "three dogs and four cats"

## Core Strategy
**ALWAYS use regional-control for 2+ objects.** Text prompts alone cannot enforce counts reliably.

### Step 1: Parse the Count Pattern
- Single type: `{count} {object}` → treat as uniform grid
- Compound (N+1): `{count} {objectA} and a {objectB}` → split into majority region + singleton region
- Compound (N+M): `{countA} {objectA} and {countB} {objectB}` → split into two independent regions

### Step 2: Design Regional Layout
**For single type (N objects):**
- Use spatial grid: "arranged in a grid", "in a row", "scattered across the scene"
- Apply per-instance emphasis: `(cat:1.2), (cat:1.2), (cat:1.2)` for count=3

**For compound scenes (N+1 or N+M):**
1. **Allocate regions by object count ratio:**
   - Example: "six cars and a kangaroo" → Region A (75% width, left): "six cars arranged in two rows", Region B (25% width, right): "one kangaroo standing"
   - Example: "a trumpet and three sheeps" → Region A (25%, left): "one trumpet on the ground", Region B (75%, right): "three sheeps grazing"

2. **Use regional-control with explicit count anchors:**
   ```
   Region A prompt: "{count_A} {object_A}, repeated {count_A} times, {spatial_hint}"
   Region B prompt: "{count_B} {object_B}, exactly {count_B}, {spatial_hint}"
   ```

3. **Add numerical tokens:** "six", "1", "three" in the regional prompt text itself

### Step 3: Apply Per-Instance Emphasis
Within EACH regional prompt, repeat the object descriptor with emphasis:
- For count=3: `(object:1.2), (object:1.2), (object:1.2)`
- For count=6: `(object:1.15), (object:1.15), (object:1.15), (object:1.15), (object:1.15), (object:1.15)`

### Step 4: Add Spatial Grid Hints
- 2 objects: "side by side"
- 3 objects: "in a triangle" or "in a row"
- 4 objects: "in a square grid"
- 5 objects: "in a pentagon" or "four corners and one center"
- 6+ objects: "arranged in rows" or "scattered evenly"

## Example Transformation
**Input:** "six cars and a kangaroo"

**Output:**
- Region A (70% left): "six red cars, (car:1.15), (car:1.15), (car:1.15), (car:1.15), (car:1.15), (car:1.15), arranged in two rows of three, parking lot"
- Region B (30% right): "one kangaroo, (kangaroo:1.3), standing upright, grassy area"
- Base prompt: "outdoor scene, clear sky, natural lighting"

## Verification
- Check regional-control is invoked with MASK coverage >= 90% of canvas
- Verify each region prompt contains numeric anchor + per-instance emphasis
- Confirm spatial hints are present in both regions