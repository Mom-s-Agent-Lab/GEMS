---
name: counting-objects
description: >-
  Enforce accurate object counts (especially 2-7+) through negative prompts preventing fusion, explicit count emphasis, per-instance enumeration, and regional conditioning fallback.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

## When to Use
Trigger when the prompt specifies an exact count of objects (two, three, four, five, six, seven, etc.) AND the verifier reports wrong counts, merged objects, or missing instances.

## Core Strategy
Diffusion models struggle with counts because:
1. They fuse multiple instances into single blurred objects
2. Attention dilutes across count words
3. Spatial reasoning is weak for precise quantities

## Implementation Steps

### Step 1: Prompt Structure for Counts 2-4
For simple counts (two to four objects):
- Use format: "exactly [NUMBER] separate [OBJECT], [NUMBER] distinct [OBJECT]"
- Example: "two metal toys" → "exactly two separate metal toys, two distinct toys"
- Add negative prompt: "single object, one, merged, fused, blurred together, conjoined"
- Boost count keyword weight: "(two:1.4) metal toys"

### Step 2: Explicit Enumeration for Counts 5+
For five or more objects:
- Enumerate instances: "first [OBJECT], second [OBJECT], third [OBJECT]..."
- Example: "six cars" → "first car, second car, third car, fourth car, fifth car, sixth car, six separate vehicles"
- Use emphasis: "(six:1.5) cars, multiple distinct cars"
- Negative: "crowd, group, merged, single mass"

### Step 3: Regional Conditioning Fallback
If base prompt fails (verifier still reports wrong count):
- Use ConditioningSetArea nodes to assign each object instance to a distinct image region
- Divide canvas into grid: 2 objects = left/right, 3-4 = 2x2 grid, 5-6 = 2x3 grid, 7+ = 3x3 grid
- Wire separate CLIPTextEncode → ConditioningSetArea for each instance
- Combine all with ConditioningCombine nodes in sequence
- Each region gets: "one single [OBJECT], isolated [OBJECT]"
- Each region negative: "multiple, two, three, group"

### Step 4: Multi-Species Scenes
For mixed counts ("four rabbits and a sheep"):
- Split into two regional prompts: one for rabbits zone, one for sheep zone
- Rabbit region: "(four:1.5) rabbits, exactly four separate rabbits, first rabbit, second rabbit, third rabbit, fourth rabbit"
- Sheep region: "one sheep, single sheep, isolated sheep"
- Negative for rabbits: "sheep, merged rabbits, three rabbits, five rabbits"
- Negative for sheep: "rabbits, multiple sheep, two sheep"

### Step 5: Unusual Attributes + Counting
When counting meets unusual materials ("seven green croissants"):
- Combine with unusual-attributes skill
- Format: "(seven:1.5) separate (green:1.4) croissants, emerald colored croissants, bright green pastries, first green croissant, second green croissant..."
- Negative: "brown croissants, tan, beige, six, eight, merged, single mass"

## Node-Level Recipe

```
For regional conditioning:
CLIPTextEncode (instance 1) → ConditioningSetArea (x=0.0, y=0.0, width=0.5, height=0.5)
CLIPTextEncode (instance 2) → ConditioningSetArea (x=0.5, y=0.0, width=0.5, height=0.5)
→ ConditioningCombine → ConditioningCombine → ... → KSampler
```

## Success Criteria
- Verifier confirms correct object count
- Each instance is spatially distinct (not merged)
- Attributes are preserved per instance
