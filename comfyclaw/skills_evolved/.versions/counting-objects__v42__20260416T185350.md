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

## When to Use
Trigger when the user requests a specific number of objects (2-10+), especially when the prompt contains number words (two, three, four, etc.) or digits followed by plural nouns.

## Core Strategy by Count Range

### 2-3 Objects
- Use spatial terms: "on the left", "on the right", "in the center"
- Example: "three cats" → "a cat on the left, a cat in the center, a cat on the right"

### 4-5 Objects
- Use explicit grid or circular arrangement
- Example: "four trucks" → "four purple trucks arranged in a 2x2 grid"
- Add "evenly spaced" to reduce clustering

### 6-7 Objects (CRITICAL ZONE - highest failure rate)
- ALWAYS use explicit grid composition: "arranged in a 3x2 grid" or "arranged in a 2x3 grid" or "in two rows"
- Add counting reinforcement: "exactly six", "precisely seven"
- Specify uniform sizing: "all the same size"
- Example: "six purple trucks" → "exactly six purple trucks of equal size arranged in two rows of three, evenly spaced"
- Example: "seven black cows" → "precisely seven black cows arranged in a grid pattern, three in front row and four in back row"
- For 7 objects specifically, use asymmetric grids: "3+4 arrangement" or "2+3+2 rows"

### 8-10 Objects
- Use regional-control skill to partition image into zones
- Specify dense packing: "tightly packed grid of eight objects"
- Consider reducing individual object size to fit all instances

### 10+ Objects
- Always invoke regional-control for zone partitioning
- Use crowd/collection language: "a crowd of", "a collection of"
- Accept approximate counts with range language

## ComfyUI Implementation
1. Query available nodes with `list_available_tools(stage="conditioning")`
2. If regional prompting nodes exist (ConditioningSetArea, ConditioningCombine), use them to assign each object to a spatial zone
3. For 6-7 objects without regional nodes, fallback to highly explicit grid language in the main prompt
4. Add negative prompt: "blurry, merged objects, overlapping, duplicate"

## Example Transformations
- "seven green croissants" → "precisely seven green croissants of identical size arranged in two rows (four in back, three in front), evenly spaced on white background"
- "six cars and a kangaroo" → "exactly six cars arranged in a 3x2 grid in the background, one kangaroo standing in the foreground center"
- "six purple trucks" → "exactly six purple trucks of equal size arranged in two neat rows of three trucks each, evenly spaced"

## Verification
After generation, if count is wrong, re-invoke with stronger grid language and consider adding ControlNet depth/segmentation if available.