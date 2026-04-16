---
name: counting-objects
description: >-
  Enforce precise object counts (2-10 items) using grid layouts, numerical emphasis, spatial anchoring, and regional fallback strategies to override diffusion model counting failures.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects (2-10 items)

## When to use
- User specifies exact counts: "five bears", "six cars", "seven croissants"
- Requested count is 2-10 objects
- Objects are distinct and countable (not crowds/swarms)

## Core problem
Diffusion models default to 1 or 3 objects regardless of prompt count. Counts ≥5 require explicit spatial scaffolding.

## Strategy by count range

### 2-4 objects
- Use regional conditioning OR explicit spatial terms
- Prompt: "(exactly COUNT:1.4) OBJECT, COUNT OBJECT arranged in a row/circle"
- Negative: "single, one, alone, trio, group"

### 5-7 objects (HIGH FAILURE ZONE)
- **Grid layout required**: "(exactly COUNT:1.5) OBJECT arranged in a grid pattern, COUNT distinct OBJECT in organized rows"
- Add spatial scaffolding: "first OBJECT on the left, second OBJECT in the center-left, third OBJECT..."
- Use regional prompting with grid cells:
  - Divide canvas into COUNT regions (2×3 grid for 6, 2×4 for 7)
  - Apply "single OBJECT" prompt to each cell
  - Set mask overlap to prevent merging
- Negative: "single, one, pair, trio, few, several, multiple, group, (COUNT-1) OBJECT, (COUNT+1) OBJECT"
- Increase CFG to 8.5-9.5 for stronger adherence

### 8-10 objects
- Always use regional prompting with labeled positions
- Prompt each region: "one OBJECT in position N"
- Consider 2-pass generation: base layout + detail refinement

## Node recipe for 5+ objects
1. Use ConditioningSetArea or regional-control skill nodes
2. Create grid: ceil(sqrt(COUNT)) rows/cols
3. For each cell: 
   - Set area coordinates
   - Condition: "single OBJECT, one OBJECT, isolated OBJECT"
   - Strength: 1.2-1.4
4. Base prompt: "(COUNT:1.5) OBJECT in organized grid arrangement, COUNT distinct items"
5. Negative: "merged, fused, overlapping, single, one, (COUNT-1), (COUNT+1)"

## Verification
- If output count ≠ target count, add regional conditioning
- If objects merge, increase area separation and add "isolated, separated, distinct" to regional prompts
- If count still fails after regional fix, reduce object complexity or switch to simpler shapes