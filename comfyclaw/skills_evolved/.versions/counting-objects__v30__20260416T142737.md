---
name: counting-objects
description: >-
  Enforce accurate object counts (2-7+) through mandatory regional-control, explicit numerical anchoring, spatial grid layouts, and per-instance attention emphasis. MUST combine with unusual-attributes for non-standard colors/materials.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# counting-objects

## When to use
Trigger when the user requests a specific number of objects/animals (two, three, four, five, six, seven, or numeric 2-7+), especially when combined with unusual attributes (colors, materials, patterns).

## Core strategy
1. **Always use regional-control** - Never rely on base prompting alone for counts ≥2
2. **Explicit numerical anchoring** - Place count at prompt start: "FOUR purple lions" not "purple lions, four of them"
3. **Per-instance prompting** - Each region gets "ONE [object]" prompt, never "four objects" in one region
4. **Spatial grid layout** - Use position tokens (left, right, center, top-left, etc.) to assign each instance a unique location
5. **Combine with unusual-attributes** - When objects have non-standard colors/materials, apply unusual-attributes prompt restructuring BEFORE splitting into regions

## Workflow modifications
1. Call unusual-attributes skill first if objects have atypical attributes
2. Restructure prompt: "[COUNT] [attributes] [object]" -> "COUNT: N" + N instances of "ONE [attribute] [object] at [position]"
3. Invoke regional-control with:
   - N regions (one per object)
   - Each region prompt: "1 [full object description], [position token], isolated, individual"
   - Negative prompt per region: "multiple, group, crowd, duplicate"
4. Use attention emphasis on count and singularity: "(one:1.3) [object]"
5. For 3-4 objects, use explicit grid: "top-left", "top-right", "bottom-left", "bottom-right" or "left", "center-left", "center-right", "right"
6. For 5+ objects, add "in a row" or "in a circle" spatial arrangement to prompt

## Example transformation
Input: "three metal zebras"
Output regions:
- Region 1: "(one:1.3) metal zebra, left side, shiny metallic texture, chrome finish, isolated"
- Region 2: "(one:1.3) metal zebra, center, shiny metallic texture, chrome finish, isolated"
- Region 3: "(one:1.3) metal zebra, right side, shiny metallic texture, chrome finish, isolated"
Global negative: "multiple zebras in one area, group, herd, duplicate, (two:1.2), (three:1.2)"

## Critical for mid-counts (3-4)
Mid-range counts fail most often. For 3-4 objects:
- Use stronger position anchors: "far left", "center", "far right" or grid corners
- Increase per-region emphasis: "(single:1.4) (one:1.4) [object]"
- Add spacing instruction to global prompt: "well-separated, distinct positions, spaced apart"

## Verification
After generation, if count is wrong, increase regional separation strength and add negative prompt weight to unwanted counts.