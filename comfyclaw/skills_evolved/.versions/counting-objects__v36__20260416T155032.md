---
name: counting-objects
description: >-
  Enforce accurate object counts (2-7+) using threshold-specific strategies: regional-control for 2-3, spatial grid anchoring + per-instance emphasis for 4-6, and layout-first conditioning for 7+.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Object Counting Strategy (2-7+ objects)

## Detection Triggers
- Number words: two, three, four, five, six, seven, eight, etc.
- Digit patterns: "4 rabbits", "6 flowers"
- Compound counts: "N [objects] and M [other objects]"

## Threshold-Based Approach

### For 2-3 Objects (Low Count)
1. Use regional-control skill with explicit spatial terms
2. Add numerical reinforcement: "exactly [number] [object], no more, no less"
3. Negative prompt: "single [object], one [object], empty"

### For 4-6 Objects (Medium-High Count) — **CURRENT FAILURE ZONE**
1. **MANDATORY**: Use regional-control with explicit grid layout
   - Divide canvas into NxM grid (e.g., 2x2 for 4, 2x3 for 6)
   - Assign ONE object per cell with position markers: "top-left", "center-right", etc.
2. **Per-instance emphasis**: Apply (emphasis:1.3) to EACH grid cell separately
3. **Spatial anchoring**: Use phrases like "arranged in two rows", "grid of [N]", "evenly spaced"
4. **Negative dilution fix**: Keep negative prompt SHORT — do not add multiple negative terms that dilute count enforcement
5. If unusual attributes involved (e.g., "green croissants"), call unusual-attributes BEFORE this skill, then integrate its output into the grid structure

### For 7+ Objects (High Count)
1. Switch to layout-first: Use ControlNet (depth/canny) with pre-composed reference showing object positions
2. Fallback: Generate in passes — base scene with 3-4, then inpaint additional instances

## Example Rewrites

**Input**: "four brown monkeys"
**Output**: "(a brown monkey in top-left:1.3), (a brown monkey in top-right:1.3), (a brown monkey in bottom-left:1.3), (a brown monkey in bottom-right:1.3), arranged in a 2x2 grid, exactly four monkeys, realistic fur"
**Negative**: "three monkeys, five monkeys, single monkey"

**Input**: "seven green croissants"
**Step 1**: Call unusual-attributes → "(vivid green:1.4) croissant, green pastry, colored dough"
**Step 2**: Apply 7-object strategy → Use ControlNet with reference layout OR generate "three green croissants" + "four green croissants" and composite

**Input**: "four rabbits and a sheep"
**Output**: "(a rabbit in top-left:1.3), (a rabbit in top-right:1.3), (a rabbit in bottom-left:1.3), (a rabbit in center-left:1.3), (a sheep in bottom-right:1.4), exactly four rabbits and one sheep, five animals total"
**Negative**: "three rabbits, five rabbits, no sheep"

## Node-Level Instructions
1. When count ≥4: ALWAYS use regional-control with grid coordinates
2. Add KSampler cfg boost: +1.0 to standard CFG for count enforcement
3. If available, inject detail-enhancing LoRA at strength 0.4-0.6 to help model distinguish instances
4. Set steps ≥25 to allow gradual instance separation

## Integration Notes
- Pair with unusual-attributes when objects have non-standard colors/materials
- Pair with spatial when objects have specific relational positions beyond grid
- For 7+ objects, escalate to controlnet-control if ControlNet models available