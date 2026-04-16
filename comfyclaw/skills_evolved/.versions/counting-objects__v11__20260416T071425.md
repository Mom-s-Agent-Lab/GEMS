---
name: counting-objects
description: >-
  Enforce precise object counts and handle multiple distinct object types in a single scene using regional conditioning, explicit numerical layout prompts, and count-specific negative prompts.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# counting-objects

## When to use
Trigger when:
- Prompt contains explicit counts ("four rabbits", "six cars", "five bears")
- Prompt contains multiple distinct object types ("backpack and a pig", "rabbits and a sheep", "cars and a kangaroo")
- Verifier reports wrong counts, missing objects, or merged object types
- fix_strategy contains "enforce_count" or "separate_object_types"

## Core strategy
For scenes with multiple object types (with or without counts):
1. **Use regional-control skill first** to establish separate conditioning zones per object type
2. **Explicit count syntax** in each regional prompt: "exactly N [object]", "precisely N [object]"
3. **Negative prompts per region**: "extra [object], fewer [object], merged [object], [other_object_type]"
4. **Layout specification**: For counts 2-7, add spatial arrangement tokens: "in a row", "in a circle", "scattered evenly", "arranged in pairs"

## Node-level implementation
**When using regional conditioning (ComfyUI nodes):**
- CLIPTextEncode per object type with count embedded
- ConditioningCombine or ConditioningConcat to merge regions
- For each region: positive="exactly N [object_type], [arrangement]", negative="extra [object_type], merged objects, [other_types]"

**Example mappings:**
- "a green backpack and a pig" → 2 regions: region1="exactly 1 green backpack", region2="exactly 1 pig"
- "four rabbits and a sheep" → 2 regions: region1="exactly 4 rabbits in a row", region2="exactly 1 sheep"
- "six cars and a kangaroo" → 2 regions: region1="exactly 6 cars arranged evenly", region2="exactly 1 kangaroo"

## Critical parameters
- CFG scale: 8-12 (higher enforcement of conditioning)
- Steps: 35-50 (counts need convergence time)
- If count still fails after regional split, increase region weight to 1.3-1.5 for the counted object

## Failure recovery
If objects still merge or counts drift:
1. Check that negative prompts exclude cross-contamination
2. Increase conditioning strength for the miscounted region
3. Add "separate" and "distinct" tokens to positive prompt
4. Consider using ControlNet (via controlnet-control skill) with a sketch showing correct count and layout