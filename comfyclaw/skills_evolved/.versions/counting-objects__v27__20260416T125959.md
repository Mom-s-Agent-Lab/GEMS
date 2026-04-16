---
name: counting-objects
description: >-
  Enforce accurate object counts (2-10+) through batch composition, per-instance regional isolation, iterative conditioning, and fusion-prevention. MUST combine with unusual-attributes for non-standard colors/materials.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

## When to Use
Trigger when the user requests a specific count of identical or similar objects (2-10+), uses phrases like "five bears", "seven croissants", "six cars", or when the verifier reports incorrect object counts.

## Critical Rules for High Counts (5+)
1. **Batch composition is mandatory** for counts ≥5: Generate single instances first, then use LatentBatch or ImageBatch nodes to compose the final count
2. **Always pair with unusual-attributes** when objects have non-standard colors/materials (green croissants, purple trucks)
3. Use regional-control only for counts 2-4; switch to batch composition for 5+

## Implementation Strategy

### For counts 2-4:
- Use RegionalPromptSimple or BREAK syntax to isolate each instance
- Explicit spatial grid: "left", "center-left", "center-right", "right"
- Emphasis on count: "(exactly three:1.4)", "only three"
- Negative: "four, five, many, crowd, group"

### For counts 5+:
1. **Generate base instance** with high emphasis on singular form:
   - Prompt: "(a single purple truck:1.5), one object only, isolated, white background"
   - Negative: "multiple, many, several, crowd"
2. **Batch replicate** using LatentBatch or ImageBatch:
   - Stack exactly N copies of the single-instance latent
   - Use ImageGridComposite or LatentComposite to arrange in grid
3. **Spatial arrangement**:
   - 5 objects: 2-row layout (3 top, 2 bottom)
   - 6 objects: 2×3 grid or 3×2 grid
   - 7+ objects: 3-row layouts (2-3-2, 3-2-2, etc.)
4. **Final composite prompt**:
   - "arranged in a grid, evenly spaced, (exactly six:1.5)"
   - Keep individual object characteristics intact

### Fusion Prevention
- Strong negative: "merged, fused, conjoined, blended, overlapping"
- Increase separation in grid layout (add padding)
- Lower CFG (6.5-7.5) to reduce over-fitting

### Node Sequence Example (count=6)
```
1. KSampler [single object, white bg] → single_latent
2. LatentBatch: batch_1=single_latent, batch_2=single_latent → pair
3. LatentBatch: batch_1=pair, batch_2=single_latent → triple
4. Repeat to build exactly 6 copies
5. LatentComposite: arrange in 2×3 grid with spacing
6. KSampler [refine grid, maintain count] → final
```

## Verification
- Check node graph includes batch composition for counts ≥5
- Verify unusual-attributes is invoked if colors/materials are non-standard
- Confirm spatial grid parameters match requested count
- Validate negative prompts include fusion-prevention terms