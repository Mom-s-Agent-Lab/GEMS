---
name: counting-objects
description: >-
  Enforce accurate object counts (2-10+) through regional prompting with explicit per-object conditioning, spatial grid layouts, and count-verification negative prompts.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

## When to Use
Trigger when the prompt contains explicit counts: "two cats", "four rabbits", "seven croissants", "5 cars", etc.

## Core Problem
Diffusion models struggle with exact counts because:
1. They lack arithmetic reasoning
2. Objects blend/merge during denoising
3. Text conditioning spreads across the image rather than localizing

## Strategy by Count Range

### 2-3 Objects: Regional Prompting
- Use regional-control skill with 2-3 distinct regions
- Each region gets ONE object with singular language
- Example: "four rabbits" → Region1: "one brown rabbit, solo", Region2: "one brown rabbit, solo", Region3: "one brown rabbit, solo", Region4: "one brown rabbit, solo"

### 4-6 Objects: Grid Layout + Regional Prompting
- Divide canvas into NxM grid (2x2 for 4, 2x3 for 6, 3x2 for 5)
- Assign ONE object per grid cell using regional prompting
- Use spatial anchors: "top-left corner", "center", "bottom-right", etc.
- CRITICAL: Use singular form in each region ("one X" not "X")

### 7+ Objects: Dense Grid + Repetition
- Use 3x3 or 4x3 grid layout
- Place objects in explicit positions: "one X in top-left, one X in top-center, one X in top-right..."
- Layer regional prompting with repetition in base prompt
- Example for 7: "seven green croissants arranged in a grid" + 7 regional prompts each saying "one green croissant, isolated, single object"

## Required Negative Prompts
ALWAYS add to prevent merging:
- "multiple heads, conjoined, merged, blended, overlapping, touching, connected, fused"
- "crowd, group, cluster, pile, stack"

## Implementation
1. Detect count word in prompt (two/three/four/2/3/4/etc.)
2. Call regional-control skill with count-specific strategy
3. For 4+: Add spatial grid structure to base prompt
4. For 7+: Use repetition ("X, X, X, X...") in base prompt PLUS regional conditioning
5. Add count-verification negative prompts
6. Use higher CFG (8-10) to enforce conditioning

## Node-Level Actions
- Use ConditioningSetArea or regional prompt nodes (IPAdapter Regional, Attention Couple, etc.)
- Create separate conditioning for each object instance
- Wire all regional conditions through ConditioningCombine
- Increase sampler steps to 35-40 for complex counts (6+)