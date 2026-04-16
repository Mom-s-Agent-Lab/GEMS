---
name: counting-objects
description: >-
  Enforce precise object counts (2-7 items) using count-specific prompt structures, regional conditioning for multi-type scenes, iterative layout verification, and graduated emphasis for high counts (5+).
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

## When to Use
Trigger when the user specifies an exact count of objects (2-7 items) using numbers or quantity words like "two", "three", "four", "five", "six", "seven". This includes both single-type scenes ("five bears") and multi-type scenes ("six cars and a kangaroo").

## Core Problem
Diffusion models have strong biases toward generating 1 or 3 items. Counts of 5+ are especially prone to failure and require aggressive intervention.

## Strategy by Count Range

### Counts 2-4 (Standard)
1. Use explicit numerical layout in prompt: "exactly [N] [objects], [N] separate [objects], [N] distinct [objects]"
2. Add count reinforcement: "COUNT:[N]"
3. Negative prompt: "single, one, solo, trio, cluster, group"

### Counts 5-7 (High Count - CRITICAL)
1. **Triple emphasis on count**: "((exactly [N] [objects])), [N] separate [objects], COUNT:[N], [N] distinct individual [objects]"
2. **Explicit spatial layout**:
   - 5 items: "arranged in a row", "five in a line", "pentagon arrangement"
   - 6 items: "two rows of three", "six in a grid", "hexagon arrangement"
   - 7 items: "seven in a row", "honeycomb pattern", "arranged across the scene"
3. **Stronger negative prompt**: "1, 2, 3, 4, single, pair, trio, few, some, several, many, cluster"
4. **Increase CFG** to 8.5-9.5 (vs standard 7-7.5) to enforce prompt adherence
5. **Higher steps**: Use 35-40 steps instead of 25-30 for better convergence

### Multi-Type Scenes (e.g., "six cars and a kangaroo")
1. Apply regional-control skill for spatial separation
2. Use counting strategy above for the high-count object
3. Isolate the single object in its own region with strong separation language

## ComfyUI Implementation
1. **Prompt structure**: Prepend count emphasis to the main positive prompt
2. **CLIPTextEncode**: No changes needed, emphasis syntax (()) is native
3. **KSampler adjustments**:
   - For counts 5-7: cfg=8.5-9.5, steps=35-40
   - For counts 2-4: cfg=7.5, steps=30
4. **Regional prompting** (if multi-type): Use regional-control skill's ConditioningSetArea nodes

## Example Transformations

**Input**: "seven green croissants"
**Output**: "((exactly 7 green croissants)), 7 separate green croissants arranged in a row, COUNT:7, 7 distinct individual green croissants, bakery display"
**Negative**: "1, 2, 3, 4, 5, 6, single, pair, trio, few, some, cluster"
**Settings**: cfg=9.0, steps=38

**Input**: "six cars and a kangaroo"
**Output**: Use regional-control with:
- Region 1 (70% width): "((exactly 6 cars)), 6 separate cars in two rows of three, COUNT:6, parking lot arrangement"
- Region 2 (30% width): "1 kangaroo, single kangaroo, one kangaroo alone"
**Settings**: cfg=8.5, steps=36

## Verification
After generation, if count appears wrong, increase emphasis to triple parentheses (((exactly [N]))), raise CFG by +1, and add more spatial layout language.