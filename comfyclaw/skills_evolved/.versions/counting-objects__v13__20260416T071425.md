---
name: counting-objects
description: >-
  Enforce precise object counts (1-10+) using count-specific prompt patterns, repetition syntax, LoRA adapters, and strategic layout instructions that scale from single objects to large groups.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# counting-objects

## When to use
Trigger when:
- User specifies an exact count: "five bears", "six trucks", "seven croissants"
- Multiple object types with counts: "six cars and a kangaroo"
- Verifier reports wrong count or missing objects
- fix_strategy contains "fix_count" or "add_counting_lora"

## Strategy by count range

### Low counts (1-2 objects)
- Use simple prompt: "a red apple", "two cats"
- No special handling needed

### Medium counts (3-4 objects)
- Use regional-control skill for spatial separation
- Explicit layout: "three dogs arranged in a row"
- Negative prompt: "fewer than 3, more than 3, wrong number"

### High counts (5-10+ objects)
**This is where standard approaches fail. Use these techniques:**

1. **Query and inject count-accuracy LoRAs first**
   - Call query_available_loras() and search for: "count", "number", "quantity", "accurate"
   - Inject with strength 0.7-0.9 before KSampler

2. **Structured enumeration syntax**
   - Instead of: "seven croissants"
   - Use: "exactly 7 croissants: first croissant, second croissant, third croissant, fourth croissant, fifth croissant, sixth croissant, seventh croissant"
   - This leverages attention repetition

3. **Grid/array layout language**
   - "arranged in a 3x2 grid", "in two rows of three"
   - "spread across the frame in a circular pattern"
   - Spatial structure helps the model distribute attention

4. **Negative prompts for count boundaries**
   - For 7 objects: "6 objects, 8 objects, fewer, more, wrong count"

5. **Increase CFG scale slightly** (7.5 → 9.0)
   - Stronger guidance helps maintain count fidelity

6. **Use EmptyLatentImage at higher resolution**
   - More spatial room = better object separation
   - Minimum 1024x1024 for counts ≥6

## Multi-type counting
For "six cars and a kangaroo":
1. Apply high-count strategy to dominant type (cars)
2. Use regional-control to separate types spatially
3. Example prompt: "6 red cars in two rows of 3 AND one kangaroo standing to the right"

## Verification
After generation, if count is still wrong:
- Add count-focused LoRA if not already present
- Increase enumeration repetition
- Switch to explicit grid layout
- Raise resolution further