---
name: counting-objects
description: >-
  Enforce precise object counts (2-7 items) using regional conditioning for multi-type scenes, explicit numerical layout prompts, count-specific negative prompts, and separate conditioning zones per object type to prevent count bleeding.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects

## Detection
Trigger when:
- Prompt contains explicit counts: "three cats", "5 birds", "two dogs and four flowers"
- Numbers 2-7 appear before object nouns
- Multiple object types with different counts in same prompt (e.g., "four rabbits and a sheep")

## Strategy

### Single Object Type (e.g., "five bears")
1. **Explicit layout prompt**: Convert count to spatial arrangement
   - 2: "two [object], side by side, pair of [object]"
   - 3: "three [object], triangle formation, trio of [object]"
   - 4: "four [object], square arrangement, quartet of [object]"
   - 5: "five [object], pentagon formation, group of exactly five [object]"
   - 6: "six [object], two rows of three, hexagon formation"
   - 7: "seven [object], circular arrangement, group of exactly seven [object]"

2. **Sampler settings**: Higher CFG (8.5-10) to enforce structure, 35-40 steps

3. **Negative prompt**: Add "single [object], one [object], trio, crowd, many, dozens"

### Multiple Object Types (e.g., "four rabbits and a sheep")
**CRITICAL**: Use regional-control skill to create separate conditioning zones

1. **Split into regions**:
   - Region 1 (70% area): "four rabbits, quartet of rabbits, group of exactly four rabbits"
   - Region 2 (30% area): "one sheep, single sheep, solitary sheep"

2. **Add count-specific negatives per region**:
   - Rabbit region: "one rabbit, two rabbits, three rabbits, five rabbits, sheep"
   - Sheep region: "multiple sheep, two sheep, rabbits"

3. **Call regional-control** with split prompts and region masks

4. **Verification tokens**: Add "photograph of exactly [count] [object]" to base prompt

## Node Configuration
- If regional-control triggered: Use ConditioningSetArea or regional prompter nodes
- Otherwise: Use standard CLIPTextEncode with enhanced count tokens
- KSampler: cfg=9.0, steps=35, scheduler=karras

## Fallback
If count still fails after regional split:
- Try ControlNet with segmentation map showing exact object positions
- Consider img2img with sketch showing count layout