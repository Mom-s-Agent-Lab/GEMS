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
Trigger when the user specifies an exact count of objects ("three cats", "five bears and a donut", "seven green croissants") or when the verifier reports wrong object counts.

## Core Strategy
1. **Always use regional-control** for counts ≥2
2. **Scale approach by count**:
   - 2-3 objects: Simple left/right or top/bottom regional split
   - 4 objects: 2×2 grid layout
   - 5-7 objects: **Mandatory explicit grid** (2×3, 2×4, or 3×3) with each cell assigned one object

## High-Count Protocol (5-7 objects)
**Critical for this failure cluster:**

### Step 1: Grid Layout Planning
- 5 objects → 2×3 grid (use 5 regions, leave 1 empty)
- 6 objects → 2×3 or 3×2 grid (fill all 6 regions)
- 7 objects → 3×3 grid (use 7 regions, leave 2 empty)

### Step 2: Regional Prompt Construction
For "seven green croissants":
```
Region 1 (top-left): "ONE green croissant, centered in frame"
Region 2 (top-center): "ONE green croissant, centered in frame"
Region 3 (top-right): "ONE green croissant, centered in frame"
Region 4 (middle-left): "ONE green croissant, centered in frame"
Region 5 (middle-center): "ONE green croissant, centered in frame"
Region 6 (middle-right): "ONE green croissant, centered in frame"
Region 7 (bottom-left): "ONE green croissant, centered in frame"
Background: "clean white background, studio lighting"
```

### Step 3: Emphasis & Anchoring
- Use "(exactly N [objects]:1.4)" in global prompt
- Each regional prompt: "ONE [object]" (spelled out)
- Add "(no duplicates:1.2)" to background prompt for 5+

### Step 4: Compound Scenes (N+M pattern)
For "five bears and a donut":
- Assign 5 regions to bears (2×3 grid, top 5 cells)
- Assign 1 region to donut (bottom-center)
- Global prompt: "(exactly five bears:1.4) and (exactly one donut:1.4)"

## Node Configuration
- Use `RegionalPromptSimple` or `RegionalConditioningCombine`
- Set region masks with equal subdivision (avoid overlap)
- Increase steps to 35-40 for counts ≥5
- Use CFG 7.5-8.5 (higher CFG improves instruction following)

## Verification
After generation, if count is still wrong:
1. Increase regional prompt strength (+0.2)
2. Simplify background (remove distractors)
3. Add negative prompt: "crowd, group, many, multiple [object]s"
4. For 7+ objects, consider splitting into two generation passes