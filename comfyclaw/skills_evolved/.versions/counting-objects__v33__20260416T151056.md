---
name: counting-objects
description: >-
  Enforce accurate object counts (2-7+) using regional-control with explicit spatial grid positioning, numerical anchoring, and per-instance emphasis. MUST use grid layouts for 4+ objects.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

## When to Use
Trigger when the user requests a specific count of objects (2 or more), especially:
- "four rabbits", "seven croissants", "six flowers"
- Multiple object types with counts: "four rabbits and a sheep"
- Any prompt with explicit numbers >= 2

## Critical Rules for 4+ Objects
For counts >= 4, you MUST:
1. Use regional-control with explicit spatial grid positioning
2. Create individual regional prompts for EACH instance
3. Use grid-based position tokens: "top-left", "top-center", "top-right", "middle-left", "center", "middle-right", "bottom-left", "bottom-center", "bottom-right"
4. Add numerical anchoring in the global prompt: "exactly [N] [objects]"

## Workflow Construction

### Step 1: Analyze the prompt
- Extract target count(s) and object type(s)
- Check if unusual-attributes skill is needed (green croissants, metal zebras, etc.)
- Determine grid layout based on count:
  - 4 objects: 2×2 grid
  - 5-6 objects: 2×3 or 3×2 grid
  - 7-9 objects: 3×3 grid

### Step 2: Build regional prompts
For "seven green croissants":
```
Global: "exactly seven croissants, bright green croissants, green pastry, emerald green bread, arranged in grid"
Region 1 (top-left): "one green croissant, top-left position"
Region 2 (top-center): "one green croissant, top-center position"
Region 3 (top-right): "one green croissant, top-right position"
Region 4 (middle-left): "one green croissant, middle-left position"
Region 5 (center): "one green croissant, center position"
Region 6 (middle-right): "one green croissant, middle-right position"
Region 7 (bottom-center): "one green croissant, bottom-center position"
```

### Step 3: Combine with other skills
- If unusual colors/materials: Apply unusual-attributes emphasis syntax
- If heterogeneous objects ("four rabbits AND a sheep"): Create separate regional chains per object type
- Add negative prompt: "multiple copies, duplicates, merged objects, blurry count"

### Step 4: Parameter tuning
- CFG: 8-10 (higher guidance for complex counting)
- Steps: 35-50 (more iterations for spatial accuracy)
- Use regional-control skill's ConditioningSetArea nodes with explicit coordinates

## For 2-3 Objects
Simpler approach:
- Use spatial skill for position keywords
- Regional-control with 2-3 regions
- Less strict grid requirement

## Verification
After generation, check:
- Exact count matches request
- No merged/overlapping instances
- Each object maintains distinct identity
- Spatial distribution is clear