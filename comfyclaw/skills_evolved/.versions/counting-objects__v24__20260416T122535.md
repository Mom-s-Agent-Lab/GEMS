---
name: counting-objects
description: >-
  Enforce accurate object counts (2-7+) through regional conditioning, spatial positioning, per-object repetition, attention emphasis, and fusion-prevention techniques. MUST combine with unusual-attributes skill when objects have non-standard colors or materials.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects

Enforce accurate counts of identical or mixed object types in generated images.

## Detection Triggers
- Numeric words: "two", "three", "four", "five", "six", "seven", "eight+"
- Phrases: "X dogs and Y cats", "a pair of", "several", "multiple"
- Any prompt specifying exact object quantities

## CRITICAL: Combine with unusual-attributes
If objects have non-standard colors/materials ("green croissants", "metal zebras", "purple trees"), FIRST invoke unusual-attributes skill to get restructured prompt, THEN apply counting techniques below. Unusual attributes + counting is a compound failure mode.

## Core Technique: Regional + Spatial + Repetition

### For 2-3 objects:
1. Use regional-control skill with separate conditioning per object
2. Add spatial positioning: "first [object] on the left, second [object] in the center, third [object] on the right"
3. Repeat object name in base prompt: "rabbit, rabbit, rabbit" for three rabbits
4. Negative prompt: "merged [objects], fused [objects], conjoined, single [object]"

### For 4-7 objects (HIGH FAILURE ZONE):
1. MANDATORY: Use regional-control with grid layout
2. Explicit spatial grid: "arranged in two rows", "spread across the frame", "evenly spaced"
3. Per-object emphasis with ascending weights:
   - "(first croissant:1.3), (second croissant:1.3), (third croissant:1.3), (fourth croissant:1.3)..."
4. Count reinforcement in base prompt: "exactly [N] [objects], [N] separate [objects], [N] individual [objects]"
5. Strong anti-fusion negative: "(merged:1.4), (fused:1.4), (overlapping:1.3), (single object:1.4), fewer than [N]"
6. If count > 5: increase canvas size to 1024x1024 minimum to provide spatial separation

### For mixed types ("four rabbits and a sheep"):
1. Regional-control with species-specific zones
2. Explicit layout: "four rabbits in the foreground, one sheep in the background"
3. Separate repetition per type: "rabbit, rabbit, rabbit, rabbit, sheep"
4. Negative: "rabbit-sheep hybrid, merged animals, transformed species"

## Node-Level Implementation
Use ComfyNode_ConditioningSetArea (regional-control) or ComfyNode_ConditioningConcat with per-object CLIPTextEncode nodes. For 4+ objects, wire multiple ConditioningSetArea nodes with non-overlapping x/y/width/height coordinates in a grid pattern.

## Failure Recovery
If verifier reports wrong count:
- Increase object emphasis weights by +0.2
- Add "group of [N]" to base prompt
- Expand negative prompt with "(incorrect count:1.5)"
- Increase resolution if objects are crowding

## Example Transformations
- "seven green croissants" → unusual-attributes FIRST → regional grid + "(first green croissant:1.3), (second green croissant:1.3)..." × 7 + "exactly seven croissants, 7 separate pastries" + negative: "(merged:1.4), (fewer than seven:1.4), (normal colored:1.3)"
- "four rabbits and a sheep" → regional split + "(first rabbit:1.3), (second rabbit:1.3), (third rabbit:1.3), (fourth rabbit:1.3), four rabbits in foreground, (one sheep:1.3), sheep in background" + negative: "(merged animals:1.4), (three rabbits:1.4), (hybrid:1.4)"