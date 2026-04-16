---
name: counting-objects
description: >-
  Enforce accurate object counts (2-10+) through mandatory regional prompting for counts ≥4, explicit spatial distribution patterns, count-locked emphasis syntax, and negative prompts that suppress under/over-generation.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

## When to Use
Trigger when the prompt specifies an exact number of objects ("three cats", "five flowers", "seven croissants") or when the verifier reports incorrect object counts.

## Strategy by Count Range

### 2-3 Objects
- Use strong emphasis: `(object:1.3)`, repeat the count token: "two cats, 2 cats"
- Add negative prompt: "single object, one, alone, solo"
- Optional: spatial hints like "side by side", "pair of"

### 4-6 Objects (HIGH FAILURE ZONE)
- **MANDATORY**: Use regional-control skill to create spatial grid
- Divide image into explicit regions: "top left", "top right", "center", "bottom left", "bottom right", "middle row"
- Assign one object per region with exact position: "a brown monkey in the top left corner, a brown monkey in the top right corner..."
- Use maximum emphasis: `(four rabbits:1.5)`, `(exactly 4:1.4)`
- Count repetition: "four rabbits, 4 rabbits, four of them"
- Negative prompt: "three, five, six, extra objects, missing objects, crowd"
- If regional control unavailable: use spatial anchoring: "four rabbits arranged in a square pattern, one in each corner"

### 7-10 Objects
- **MANDATORY**: Regional prompting with geometric layout patterns
- Use arrangement language: "seven croissants arranged in a circle", "eight flowers in two rows of four"
- Break into sub-groups: "three in front row, four in back row"
- Maximum emphasis and triple repetition: `(seven:1.5)`, "seven green croissants, 7 croissants, exactly seven"
- Negative: "six, eight, pile, heap, many, several, few"

### 10+ Objects
- Use geometric patterns: "grid of", "circle of", "two rows of five"
- Consider iterative generation or ControlNet if available

## Multi-Object Scenes (e.g., "four rabbits and a sheep")
- Apply counting strategy to EACH object type separately
- Use regional-control to separate object types into distinct zones
- Example: "four rabbits in the left half (arrange in 2x2 grid), one sheep in the right half"
- Emphasize both counts independently: `(four rabbits:1.4)`, `(one sheep:1.3)`

## Critical Rules
- For counts ≥4: regional prompting is NOT optional — it's required
- Always add count-specific negative prompts
- Test and verify: if output fails, increase emphasis and add more spatial specificity
- Spatial distribution prevents model from "clumping" objects into ambiguous groups