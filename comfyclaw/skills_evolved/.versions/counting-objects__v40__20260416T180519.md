---
name: counting-objects
description: >-
  Enforce accurate object counts (2-10+) through explicit regional prompting, spatial anchoring, and count-specific strategies tailored to each quantity range.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

Trigger when: User requests specific counts of objects ("three cats", "four dogs", "five flowers") or verifier reports incorrect object count.

## Strategy by Count Range

### 2 objects
- Use simple regional prompting with left/right split
- Prompt structure: "[object 1] on the left side, [object 2] on the right side"
- Add spatial separation tokens: "separated", "distinct", "individual"

### 3-4 objects (CRITICAL RANGE)
- Use explicit grid positioning language in the prompt
- For 3: "[object] in foreground left, [object] in foreground center, [object] in foreground right, three total, trio arrangement"
- For 4: "[object] in top left, [object] in top right, [object] in bottom left, [object] in bottom right, four total, 2x2 grid, quadrant layout"
- Add count reinforcement: append "exactly [number] [objects]" to prompt
- Use negative prompt: "one, two, five, six, seven, crowd, many, group" (exclude wrong counts)
- Consider adding "lineup", "arranged", "separated" to force distinct instances
- If regional-control skill available, invoke it with per-quadrant prompts

### 5-6 objects
- Switch to circular or pentagon arrangement language
- Prompt: "[object] arranged in a circle, five distinct [objects], pentagonal formation"
- Add "each clearly visible, separated, spaced apart"

### 7+ objects
- Use rows strategy: "two rows of [objects], [X] in front row and [Y] in back row"
- Consider ControlNet tile grid if available (check via regional-control or controlnet-control skills)
- Add "lineup", "array", "grid formation"

## Implementation Checklist
1. Identify target count from user prompt
2. Select strategy from ranges above
3. Rewrite prompt with spatial anchors and count reinforcement
4. Add negative prompt with wrong counts
5. If count > 4 and regional-control available, delegate to that skill
6. Set CFG slightly higher (8-10) to improve prompt adherence
7. Consider multiple generation attempts with seed variation

## Key Principles
- Explicit spatial language beats implicit counting
- Reinforce count in multiple ways (number word + arrangement type + "exactly N")
- Negative prompts prevent model from defaulting to typical counts
- Regional prompting becomes mandatory at 4+ objects