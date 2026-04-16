---
name: multi-category
description: >-
  Generate scenes with semantically distinct object categories (animals+objects, vehicles+nature, food+creatures) using mandatory regional prompting with explicit coordinate masking, per-category positive conditioning, count verification, and category-isolation negative prompts.
license: MIT
metadata:
  cluster: "multiple_object_types"
  origin: "self-evolve"
---

# Multi-Category Object Generation

## When to Use
Trigger when the prompt contains objects from 2+ distinct semantic categories:
- Animal + manufactured object (pig + backpack, kangaroo + car)
- Animal + animal (rabbits + sheep, bears + birds)
- Vehicle + nature (cars + flowers, truck + trees)
- Food + creature (donut + bears, pizza + cats)
- Any combination where object priors strongly differ

## Why It Fails Without This Skill
Diffusion models merge semantically distant categories into hybrid forms or drop the less-dominant category entirely. "A pig and a backpack" often produces only the pig, or a pig with backpack-colored patches.

## Required Approach
**MANDATORY: Use regional prompting with spatial separation. Never attempt multi-category scenes with a single global prompt.**

### Step 1: Parse and Separate Categories
Identify each distinct object type and its count:
- "a green backpack and a pig" → Object1: backpack(1, green), Object2: pig(1)
- "four rabbits and a sheep" → Object1: rabbits(4), Object2: sheep(1)
- "six cars and a kangaroo" → Object1: cars(6), Object2: kangaroo(1)

### Step 2: Allocate Spatial Regions
Divide the canvas into non-overlapping regions. Use these coordinate patterns:
- 2 objects: left half (0.0-0.5 x-range) vs right half (0.5-1.0 x-range)
- 3+ objects of same category + 1 different: grid for multiples (0.0-0.7), single region for unique (0.7-1.0)
- For counts >4: use 2x2 or 3x2 grid layouts with explicit per-cell coordinates

### Step 3: Configure Regional Prompting Nodes
For each category:
1. **create_regional_prompt_node** with:
   - prompt: "[COUNT] [ATTRIBUTES] [OBJECT], isolated, [MATERIAL/COLOR tokens], highly detailed"
   - mask_coords: explicit x1,y1,x2,y2 based on Step 2
   - strength: 1.0
   - Example: "1 green leather backpack, isolated, product photography" at (0.0, 0.3, 0.5, 0.9)

2. **Add category-isolation negative prompt per region**:
   - If region is for "backpack", negative: "pig, animal, fur, snout, organic"
   - If region is for "pig", negative: "backpack, fabric, zipper, straps, manufactured"

### Step 4: Global Negative Prompt
Add to base negative: "merged objects, hybrid creatures, morphed forms, blended categories, object fusion"

### Step 5: Verification Tokens
In global positive prompt, append: "[COUNT1] [OBJECT1] AND [COUNT2] [OBJECT2], clearly separated, distinct entities"
Example: "1 backpack AND 1 pig, clearly separated, distinct entities"

### Step 6: Sampler Settings
- cfg_scale: 8.5-10.0 (higher CFG enforces regional boundaries)
- steps: 35+ (complex scenes need more denoising iterations)
- If using SDXL: set refiner at 0.7 to sharpen category boundaries

## Node Sequence
```
CLIPTextEncode (global positive + verification tokens)
  ↓
RegionalPromptNode1 (category 1, mask A, negative=category2 tokens)
  ↓
RegionalPromptNode2 (category 2, mask B, negative=category1 tokens)
  ↓
[...additional regions if needed]
  ↓
ConditioningCombine (merge all regional conditionings)
  ↓
KSampler (cfg=9.0, steps=35)
```

## Common Mistakes to Avoid
- ❌ Using single prompt for multiple categories
- ❌ Overlapping regional masks
- ❌ Forgetting category-isolation negatives
- ❌ CFG < 8.0 (too weak to enforce separation)
- ❌ Not explicitly stating counts in verification tokens

## Success Criteria
- All categories present in output
- No hybrid/morphed forms
- Correct counts for each object type
- Attributes (color, material) correctly bound to intended objects