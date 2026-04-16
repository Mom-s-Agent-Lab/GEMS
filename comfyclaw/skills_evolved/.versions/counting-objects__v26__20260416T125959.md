---
name: counting-objects
description: >-
  Enforce accurate object counts (2-7+) through per-instance regional isolation, explicit spatial grid layouts, attention emphasis, and fusion-prevention. MUST combine with unusual-attributes for non-standard colors/materials.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects

## When to Use
Trigger when the prompt contains explicit counts: "two cats", "three metal zebras", "four purple lions", "five spotted birds", etc. Also trigger when verifier reports wrong object count or merged/fused instances.

## Core Strategy
Diffusion models struggle with counts >2 because:
- Objects merge into amorphous blobs
- The model satisfies "multipleness" without exact counting
- Identical objects lack distinguishing features to separate them

## Required Techniques (use ALL for counts ≥3)

### 1. Mandatory Skill Combination
**CRITICAL**: If objects have unusual attributes (colors, materials), you MUST trigger `unusual-attributes` skill FIRST, then apply counting techniques to the restructured prompt.
- "three metal zebras" → unusual-attributes (metal) + counting (three)
- "four purple lions" → unusual-attributes (purple) + counting (four)
- "four spotted birds" → counting only (spotted is natural)

### 2. Per-Instance Spatial Grid
Assign explicit positions using grid layout language:
- 2 objects: "one [object] on the left side, one [object] on the right side"
- 3 objects: "one [object] in the center, one [object] on the left, one [object] on the right"
- 4 objects: "one [object] in top-left, one [object] in top-right, one [object] in bottom-left, one [object] in bottom-right"
- 5+ objects: Use "arranged in a row" or "arranged in a circle" with ordinal positions

### 3. Repetition with Separators
Repeat the object description N times with spatial separators:
```
"a purple lion in top-left, a purple lion in top-right, a purple lion in bottom-left, a purple lion in bottom-right"
```

### 4. Attention Emphasis on Count
Wrap the count number in multiple parentheses:
```
"(((four))) distinct purple lions, 4 separate lions"
```

### 5. Fusion Prevention (Negative Prompt)
Add to negative prompt:
```
"merged objects, fused animals, conjoined, amorphous blob, single mass"
```

### 6. Regional Conditioning (if available)
Use `regional-control` skill to create separate conditioning regions:
- Divide canvas into N regions
- Apply identical prompt to each region
- Prevents cross-region fusion

## Example Transformations

**Input**: "three metal zebras"
**Step 1 (unusual-attributes)**: "(metal zebra:1.4), (metallic texture:1.3), chrome surface, steel zebra, NOT organic, NOT fur"
**Step 2 (counting)**: "(((three))) distinct metal zebras, one metallic zebra on the left, one metallic zebra in the center, one metallic zebra on the right, 3 separate chrome zebras"
**Negative**: "merged zebras, fused metal, single blob, two zebras, four zebras"

**Input**: "four purple lions"
**Step 1 (unusual-attributes)**: "(purple lion:1.4), (vivid purple fur:1.3), violet mane, magenta lion, NOT brown, NOT tan"
**Step 2 (counting)**: "(((four))) distinct purple lions, one purple lion in top-left corner, one purple lion in top-right corner, one purple lion in bottom-left corner, one purple lion in bottom-right corner, 4 separate violet lions"
**Negative**: "merged lions, fused animals, three lions, five lions, brown lion, normal colored lion"

## Workflow Adjustments
- Increase CFG to 8-10 (stronger prompt adherence)
- Use sampler with good composition (dpmpp_2m or euler_a)
- Consider higher resolution (1024x1024+) to give objects space
- Steps: 30-40 for complex counting scenes

## Verification
After generation, check:
- Exact count matches request
- Each instance is spatially separated
- No merged/conjoined objects
- Attributes applied uniformly across all instances