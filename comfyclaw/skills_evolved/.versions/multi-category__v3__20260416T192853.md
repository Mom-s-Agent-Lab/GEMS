---
name: multi-category
description: >-
  Generate scenes with semantically distinct object categories (animals+objects, vehicles+nature, food+creatures) using regional prompting, count enforcement, and category isolation to prevent cross-contamination.
license: MIT
metadata:
  cluster: "multiple_object_types"
  origin: "self-evolve"
---

# Multi-Category Object Generation

## When to Use
Trigger when the prompt contains TWO OR MORE semantically distinct object categories in the same scene:
- Animals + objects (pig and backpack, rabbits and sheep)
- Vehicles + nature (cars and kangaroo, truck and flowers)
- Food + creatures (bears and donut)
- Any mix where categories have different visual priors

## Core Problem
Diffusion models blend features across categories — fur textures bleed onto objects, animal colors contaminate vehicles, counts get confused when multiple types coexist.

## Solution Strategy

### 1. Detect Categories and Counts
Parse the prompt to identify:
- Category A: object type + count (if specified)
- Category B: object type + count (if specified)

### 2. Invoke Complementary Skills
- **counting-objects**: If ANY category has a numeric count ("four rabbits", "six cars"), invoke this skill FIRST to get count-enforcement syntax
- **regional-control**: ALWAYS invoke to create separate conditioning regions for each category

### 3. Category Isolation Syntax
Restructure prompt using:
```
[Category A with count], isolated, distinct | [Category B with count], separate, individual
```

Add negative prompt:
```
(merged:1.3), (blended:1.3), (hybrid:1.2), fused, combined, mixed features
```

### 4. Regional Prompting Setup
- Region 1 (60% image): Category A + "no [Category B]"
- Region 2 (40% image): Category B + "no [Category A]"
- Mask overlap: 10% transition zone only

### 5. Sampler Adjustments
- CFG scale: 8.5-9.5 (higher guidance prevents category mixing)
- Steps: 35+ (more steps = better category separation)

## Example Transformation
**Input:** "four rabbits and a sheep"

**After counting-objects:** "four rabbits, 1 2 3 4, individual rabbits separated"

**After multi-category:**
```
Prompt: "four rabbits, distinct individual animals | one sheep, separate animal, isolated"
Negative: "(merged animals:1.3), (blended:1.3), rabbit-sheep hybrid"
```

**Regional setup:**
- Region 1: "four rabbits, no sheep"
- Region 2: "one sheep, no rabbits"

## Node-Level Actions
1. Call `query_skill('counting-objects')` if counts present
2. Call `query_skill('regional-control')` always
3. Use `CLIPTextEncode` with category-isolated positive prompt
4. Use separate `CLIPTextEncode` for strong negative prompt
5. Configure `KSampler`: cfg=9.0, steps=40

## Validation
Verify output contains:
- Correct count for each category
- No feature blending (fur on metal, scales on fabric)
- Spatial separation between categories