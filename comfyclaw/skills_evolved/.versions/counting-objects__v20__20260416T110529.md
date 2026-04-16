---
name: counting-objects
description: >-
  Enforce accurate object counts (2-7+) through regional conditioning with physical separation, explicit enumeration, count emphasis, and negative prompts preventing fusion.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

## Purpose
Generate the exact number of requested objects, especially counts ≥4 where standard prompting fails.

## When to Use
- User specifies a count: "three cats", "five apples", "seven birds"
- Count words: two, three, four, five, six, seven, eight, nine, ten
- Plurals with implicit count: "several", "many", "a few"
- Verifier reports wrong count or merged objects

## Critical Rule for 4+ Objects
**If count ≥ 4, ALWAYS use regional-control skill.** Standard prompting cannot reliably separate 4+ instances.

## Implementation Strategy

### For counts 2-3 (optional regional):
1. **Explicit enumeration** in prompt:
   - "(first cat:1.3), (second cat:1.3), (third cat:1.3)"
   - "one dog, two dog, three dog"

2. **Strong count emphasis**:
   - "(exactly three:1.4) brown monkeys, (three monkeys:1.3)"

3. **Anti-fusion negative prompt**:
   - "merged, fused, conjoined, blurred together, overlapping bodies, single object"

### For counts ≥4 (MANDATORY regional):
1. **Call regional-control skill** to create spatial grid layout
2. Create one region per object instance with individual conditioning
3. Use physical separation (grid positions) to prevent merging
4. Example for "four rabbits":
   - Region 1 (top-left): "first rabbit, single rabbit"
   - Region 2 (top-right): "second rabbit, single rabbit"
   - Region 3 (bottom-left): "third rabbit, single rabbit"
   - Region 4 (bottom-right): "fourth rabbit, single rabbit"

5. **Background region** should contain scene context only:
   - "grass field, outdoor setting" (no animal mentions)

### ComfyUI Node Pattern (via regional-control):
- Use `ConditioningSetArea` or `regional_conditioning` custom nodes
- Define non-overlapping regions (each ~1/N of canvas)
- Apply separate `CLIPTextEncode` per region
- Combine with `ConditioningCombine` before KSampler

## Fallback (if regional fails)
- Increase steps to 40+
- CFG 8-10 for stronger prompt adherence
- Add "separate individuals" to positive prompt
- Seed sweep (try 5 different seeds)

## When to Skip
- Single object ("a cat")
- Uncounted plurals where exact number doesn't matter ("some clouds")