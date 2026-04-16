---
name: counting-objects
description: >-
  Enforce accurate object counts (2-7+) through numerical emphasis, repetition, regional prompting, and iterative verification with count-specific negative prompts.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects (2-7+)

## When to use
- User specifies exact counts: "three cats", "five apples", "7 books"
- Counts of 4+ objects (highest failure rate)
- Mixed counts: "four rabbits and a sheep"

## Core strategy
Diffusion models merge/drop objects at counts ≥4. Counter with:

### 1. Triple-redundant count encoding
In the prompt, express count THREE ways:
```
(4) four separate distinct individual brown monkeys, 4 monkeys total
```
- Numerical: `(4)` or `4`
- Written: `four`
- Reinforcement: `separate distinct individual` + `total`

### 2. Spatial distribution (critical for 4+)
Force physical separation:
```
four rabbits arranged in a row, spaced apart, one rabbit on far left, one rabbit in center-left, one rabbit in center-right, one rabbit on far right
```

### 3. Regional prompting (use for counts ≥4)
Create separate conditioning regions:
- Divide canvas into N regions
- Apply "one [object]" prompt to each region
- Use ComfyUI regional conditioning nodes or attention masks

### 4. Negative prompt anti-fusion
```
Negative: merged objects, fused [object-type], single [object], overlapping [object-type], blended [object-type]
```

### 5. Counting-optimized parameters
- CFG: 8-10 (higher adherence)
- Steps: 35-40 (more refinement)
- Resolution: 1024×768 or wider (space for separation)

### 6. Iterative verification
After generation:
- Count objects in output
- If count wrong, regenerate with:
  - Higher CFG (+1.5)
  - Added spatial terms: "clearly separated", "distinct spaces"
  - Stronger emphasis: `((4))` instead of `(4)`

## Example transforms

**Before:** "seven green croissants"

**After:** "(7) seven separate distinct individual green croissants, arranged in a line with clear spacing between each croissant, 7 croissants total, vibrant green color on each croissant | Negative: merged croissants, fused pastries, single croissant, overlapping croissants"

**Before:** "four rabbits and a sheep"

**After:** "(4) four separate white rabbits positioned in different locations, spaced apart from each other, AND (1) one single brown sheep in the center, 4 rabbits total, 1 sheep total | Negative: merged animals, fused rabbits, rabbit-sheep hybrid, overlapping animals"

## Node-level implementation
If using regional prompting:
1. Use `ConditioningSetArea` or `RegionalConditioner` nodes
2. Split image into N vertical or grid regions
3. Apply "one [object]" prompt to each region with mask
4. Combine with `ConditioningCombine`

## Failure recovery
If output has wrong count:
- Increase emphasis weight: `(4)` → `((4))` → `(((4)))`
- Add enumeration: "first [object], second [object], third [object], fourth [object]"
- Reduce sampler randomness: lower CFG by 1, switch to dpmpp_2m sampler