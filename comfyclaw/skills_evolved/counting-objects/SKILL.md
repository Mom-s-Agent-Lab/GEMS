---
name: counting-objects
description: >-
  Enforce accurate object counts (2-10+) through count-tiered strategies: regional prompting for 2-3 objects, explicit grid anchoring for 4-6, and repetition+spatial distribution for 7+.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# counting-objects

## Purpose
Generate exact counts of identical or similar objects when the user specifies a number (two, three, four, five, six, seven, etc.). Diffusion models default to 1-2 objects and hallucinate counts above 3 without structural intervention.

## When to Use
- User prompt contains number words: "two cats", "four rabbits", "five apples", "seven croissants", "ten stars"
- Verifier reports wrong object count
- fix_strategy contains "enforce_count" or "add_regional_prompt"

## Strategy by Count Range

### 2-3 Objects: Regional Prompting
- Use regional-control skill with explicit LEFT/RIGHT or spatial anchors
- Example: "four rabbits" → "REGION_LEFT: two brown rabbits, REGION_RIGHT: two brown rabbits"

### 4-6 Objects: Grid Anchoring + Repetition
- Use regional-control with EXPLICIT grid layout (top-left, top-right, bottom-left, bottom-right, center-left, center-right)
- Add count-specific emphasis: (four rabbits:1.4), exactly four, 4 rabbits
- Negative prompt: "one rabbit, two rabbits, three rabbits, five rabbits"
- Example: "six cars" → "REGION_TOP: three red cars in a row, REGION_BOTTOM: three red cars in a row, (exactly six cars:1.3)"

### 7+ Objects: Spatial Distribution + Strong Repetition
- Use scattered/crowd composition keywords: "group of seven", "crowd of", "collection of", "array of"
- Repeat object noun 3-4 times: "seven green croissants, croissant, croissant, croissant, multiple croissants"
- Add layout hints: "arranged in a circle", "scattered across the scene", "in rows"
- High emphasis: (seven croissants:1.5)
- Negative: "one, two, three, four, five, six, eight, nine"

## Multi-Category Scenes
When count appears with multiple object types ("four rabbits and a sheep"):
1. Apply counting strategy to the plural object (four rabbits)
2. Use multi-category skill to isolate categories
3. Example: "REGION_LEFT: four brown rabbits, rabbit, rabbit, (exactly four rabbits:1.3) | REGION_RIGHT: one white sheep, single sheep"

## Node Instructions
- Always use regional-control or CLIPTextEncodeSDXLRefiner with separate conditionings
- For 4+ objects, increase CFG to 8-9 for stronger prompt adherence
- Consider hires-fix to sharpen individual object details
- Never rely on base prompt alone for counts above 3

## Critical Rules
- Counts of 4+ REQUIRE regional/grid layout — prompting alone fails
- Always include negative prompts with wrong counts
- Repeat the object noun proportional to count (4 objects = 2-3 repetitions, 7+ = 3-4 repetitions)
- Use emphasis syntax (count:1.3-1.5) for all counts