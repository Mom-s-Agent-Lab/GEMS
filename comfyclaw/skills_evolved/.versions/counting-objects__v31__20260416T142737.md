---
name: counting-objects
description: >-
  Generate exact counts of multiple objects (2-7+) using regional conditioning, spatial grid layouts, and instance-separation techniques
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

## When to Use
Trigger when:
- User requests specific counts: "four rabbits", "seven croissants", "three zebras"
- Generating 2+ instances of the same object type
- Verifier reports wrong object count or merged instances
- fix_strategy contains "enforce_count" or "add_regional_prompt"

## Core Strategy
Diffusion models merge repeated objects into blobs. Fix this through:
1. **Spatial grid layout** - divide canvas into non-overlapping regions
2. **Per-region conditioning** - one prompt per instance with position anchors
3. **Instance separation** - negative prompts to prevent merging
4. **Distinct markers** - when combined with unusual-attributes, use colors/materials to differentiate

## Node-Level Instructions

### Step 1: Calculate Grid Layout
For N objects, choose grid dimensions:
- 2 objects: 1x2 or 2x1 horizontal/vertical
- 3 objects: 1x3 or 3x1 row
- 4 objects: 2x2 grid
- 5-6 objects: 2x3 or 3x2 grid
- 7+ objects: 3x3 grid

Divide latent dimensions by grid cells to get region sizes.

### Step 2: Create Base Conditioning
Start with global prompt describing the scene, then branch into regions.

### Step 3: Apply Regional Conditioning (ConditioningSetArea)
For EACH object instance:
```
ConditioningSetArea(
  conditioning=base_conditioning,
  width=cell_width,
  height=cell_height,
  x=cell_x_offset,
  y=cell_y_offset,
  strength=1.2  # Boost per-region strength
)
```

Prompt structure per region:
- "a single [object], [position anchor], [distinctive feature if using unusual-attributes]"
- Example: "a single green croissant, left side, vibrant green color"
- Include ordinal anchors: "first rabbit", "second rabbit", etc.

### Step 4: Combine Regional Conditions
Use ConditioningCombine to merge all regional conditions:
```
combined = ConditioningCombine(region_1, region_2)
combined = ConditioningCombine(combined, region_3)
# ... continue for all regions
```

### Step 5: Add Negative Prompt for Instance Separation
Enhance negative prompt with:
- "merged objects, overlapping [object_type], fused [object_type], blurry boundaries"
- "single large [object_type], one [object_type]"

### Step 6: Integration with unusual-attributes
When prompt contains non-standard colors/materials (detected by unusual-attributes trigger):
- Let unusual-attributes handle color/material emphasis syntax
- In regional prompts, include the color/material as instance identifier
- Example: "green croissant" in region 1, "green croissant" in region 2, etc.
- This creates distinct visual anchors per instance

### Step 7: Sampler Settings
- Use higher step count (35-50) to resolve spatial conflicts
- CFG 7.5-9.0 to strengthen conditioning adherence
- Consider using DPM++ 2M or Euler a for better spatial separation

## Failure Modes
- **Objects still merge**: Increase regional strength to 1.3-1.5, reduce cell overlap
- **Missing objects**: Check ConditioningCombine chain includes all regions
- **Wrong positions**: Verify x,y offsets match grid calculation
- **Identical appearance prevents counting**: Ensure unusual-attributes is also triggered for visual differentiation

## Example Workflow Fragment
```
For "four brown monkeys":
Grid: 2x2, latent 1024x1024 -> cells 512x512

region_1 = ConditioningSetArea(base, 512, 512, 0, 0, 1.2)
  prompt: "first brown monkey, top left, individual monkey"
region_2 = ConditioningSetArea(base, 512, 512, 512, 0, 1.2)
  prompt: "second brown monkey, top right, individual monkey"
region_3 = ConditioningSetArea(base, 512, 512, 0, 512, 1.2)
  prompt: "third brown monkey, bottom left, individual monkey"
region_4 = ConditioningSetArea(base, 512, 512, 512, 512, 1.2)
  prompt: "fourth brown monkey, bottom right, individual monkey"

combined = ConditioningCombine(ConditioningCombine(ConditioningCombine(region_1, region_2), region_3), region_4)

negative: "merged monkeys, overlapping monkeys, fused animals, single large monkey, blurry boundaries"
```