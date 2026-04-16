---
name: counting-objects
description: >-
  Enforce precise object counts (especially 3-4 objects) using tiered strategies: count-specific prompting for 1-2 objects, explicit spatial grid layouts + regional conditioning for 3-4 objects, and full regional decomposition for 5+ objects.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

## When to Use
Trigger when the prompt contains explicit counts ("three cats", "four dogs", "5 birds") or multiple distinct object types that need to appear together.

## Strategy by Count Range

### 1-2 Objects
- Use standard prompting with count keywords: "exactly two", "a pair of", "single"
- Add negative prompt: "three, four, many, multiple, crowd, group"

### 3-4 Objects (CRITICAL RANGE)
This range fails most often — use ALL of these together:

1. **Explicit spatial layout in prompt:**
   - For 3: "three [objects] arranged in a triangle, one in front and two behind"
   - For 4: "four [objects] in a square formation, two in front and two in back" OR "four [objects] in a horizontal row"

2. **Regional conditioning (MANDATORY for 3-4):**
   - Use RegionalPromptSimple or equivalent
   - Divide canvas into quadrants or thirds
   - Assign one object per region with explicit position: "left [object]", "center [object]", "right [object]"
   - Each region prompt: "single [object], [attributes], isolated, alone"

3. **Prompt structure:**
   - Main prompt: "exactly [number] [objects], [spatial layout], each [object] clearly visible and distinct"
   - Emphasize count: "(three [objects]:1.3)" or "(four [objects]:1.3)"
   - Add attributes to differentiate: "three metal zebras: left zebra, center zebra, right zebra"

4. **Negative prompt reinforcement:**
   - Wrong counts: "two, five, six, many, crowd, herd"
   - Merged objects: "fused, merged, overlapping, blended together"

### 5+ Objects
- Full regional decomposition required
- Create grid layout (2×3 for 6, 3×3 for 9, etc.)
- One regional prompt per object with strict boundaries
- Background prompt to fill empty space

## ComfyUI Implementation

### For 3-4 objects (use ConditioningSetArea or RegionalPromptSimple):
```
1. Split image into regions based on count
2. For each region:
   - Create separate conditioning with "single [object], [position]"
   - Set area boundaries (x, y, width, height)
   - Strength: 0.8-1.0
3. Combine all regional conditionings
4. Add global negative conditioning with wrong counts
```

### Validation
After generation, check output for:
- Correct count (use verification step if available)
- Each object clearly separated
- No merged/fused instances

## Examples

**"four brown monkeys":**
- Main: "exactly four brown monkeys in a square formation, two monkeys in front and two monkeys in back, each monkey clearly visible"
- Regional 1 (front-left): "single brown monkey, front left position, isolated"
- Regional 2 (front-right): "single brown monkey, front right position, isolated"
- Regional 3 (back-left): "single brown monkey, back left position, isolated"
- Regional 4 (back-right): "single brown monkey, back right position, isolated"
- Negative: "three monkeys, five monkeys, many monkeys, crowd, fused, merged"

**"three metal zebras":**
- Main: "exactly three metal zebras in a triangle arrangement, one zebra in front and two zebras behind, metal texture"
- Regional 1 (center-front): "single metal zebra, front center, chrome texture"
- Regional 2 (left-back): "single metal zebra, back left, chrome texture"
- Regional 3 (right-back): "single metal zebra, back right, chrome texture"
- Negative: "two zebras, four zebras, many zebras, herd, overlapping zebras"