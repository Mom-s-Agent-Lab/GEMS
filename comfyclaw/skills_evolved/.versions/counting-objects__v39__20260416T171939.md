---
name: counting-objects
description: >-
  Enforce accurate object counts (2-10+) through per-instance regional prompting with explicit spatial anchors, negative prompts to suppress extras, and mandatory position verification for counts ≥5.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects

## Trigger Conditions
- User prompt contains number words (two, three, four, five, six, seven, eight, nine, ten) or digits followed by plural nouns
- Verifier reports wrong object count, missing instances, or duplicated objects
- fix_strategy contains 'enforce_count' or 'add_regional_prompt'

## Strategy by Count Range

### 2-4 Objects: Regional Prompting
1. Use ConditioningSetArea or regional prompt nodes
2. Divide canvas into equal regions (2 objects: left/right; 3 objects: left/center/right; 4 objects: quadrants)
3. Apply separate CLIP conditioning per region with individual object descriptions
4. Add position tokens: "on the left side", "in the center", "top right corner"
5. Negative prompt: "crowd, group, extras, multiple copies"

### 5-7 Objects: Explicit Spatial Grid + Individual Anchoring
1. **Mandatory**: Use regional prompting with one region per object
2. For 5 objects: use pentagon layout (one center, four corners)
3. For 6 objects: use 2×3 or 3×2 grid
4. For 7 objects: use hexagon + center (6 around perimeter, 1 center)
5. **Critical**: Each region gets explicit coordinates and spatial anchor:
   - "[object] positioned at top left corner"
   - "[object] in the exact center"
   - "[object] at bottom right"
6. Set region strength to 1.2-1.5 to enforce boundaries
7. Add to main positive prompt: "arranged in a grid, evenly spaced, distinct positions"
8. Add to negative prompt: "overlapping, clustered, merged, extra copies, missing items, {count+1} [objects], {count+2} [objects]"
9. Increase sampling steps by 50% (e.g., 20→30) for count enforcement

### 8-10 Objects: Fallback to ControlNet Segmentation
1. Generate a reference segmentation mask with colored regions (one color per object)
2. Load ControlNet with seg or tile preprocessor
3. Apply regional prompting as above but with ControlNet guidance
4. Set ControlNet strength to 0.7-0.9
5. Use negative prompt: "extras, duplicates, {count+1} or more [objects]"

## Node Configuration
- **ConditioningSetArea** inputs: conditioning, width, height, x, y, strength=1.3
- **ConditioningCombine**: chain all regional conditionings together
- For unusual attributes (green croissants, stone animals), apply unusual-attributes FIRST, then apply this skill's regional structure
- Sampler: increase steps by 30-50% for counts ≥5
- CFG scale: raise to 8-10 for count enforcement

## Verification
After generation, prompt the verifier to count objects explicitly. If count is wrong, retry with:
1. Stronger regional boundaries (+0.2 strength)
2. More explicit negative prompt listing wrong counts
3. Add "exactly {count} [objects], no more, no less" to positive prompt