---
name: counting-objects
description: >-
  Enforce accurate object counts (2-10+) through tiered strategies: regional prompting for 2-4 objects, iterative composition or attention masking for 5-7 objects, and ControlNet spatial grids for 8+ objects.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects

## When to Use
Trigger when the prompt specifies an exact object count ≥2 ("five bears", "six cars", "seven croissants"). Also use when verifier reports count mismatch.

## Strategy Tiers

### Tier 1: Counts 2-4 (Regional Prompting)
- Use RegionalPromptSimple or ConditioningSetMask
- Divide canvas into N equal regions (grid or horizontal/vertical strips)
- Apply one object prompt per region with emphasis: "(bear:1.3) in foreground"
- Add global negative: "crowd, group, merged objects, duplicates"

### Tier 2: Counts 5-7 (Iterative Composition)
- **Primary method**: Use LatentComposite to build the scene in 2 passes
  - Pass 1: Generate first 3-4 objects with Tier 1 strategy
  - Pass 2: Generate remaining objects in masked regions, composite onto Pass 1 latent
- **Alternative**: Use attention masking nodes (AttentionCouple) to isolate each instance
- Place objects in explicit spatial arrangements: "arranged in a circle", "in two rows", "spread across the scene"

### Tier 3: Counts 8+ (ControlNet Grid)
- Generate a simple grid/dot pattern as ControlNet input (use EmptyImage + drawing nodes)
- Apply ControlNet with low strength (0.4-0.6) to anchor spatial positions
- Combine with regional prompting for per-object attributes

## Prompt Reinforcement (All Tiers)
- Embed count in prompt: "exactly six cars, 6 cars total, six distinct vehicles"
- Use numbered lists: "first car, second car, third car..."
- Add negative: "missing objects, incomplete count, only N-1 objects"
- For unusual attributes ("green croissants"), preserve attribute emphasis per region: "(green:1.4) (croissant:1.3)"

## Verification
- If verifier still reports count mismatch after Tier 1, escalate to Tier 2
- If Tier 2 fails, escalate to Tier 3 (ControlNet)
- For 7+ objects, start directly at Tier 2 or 3

## Node Sequence (Tier 2 Example)
1. EmptySD3LatentImage -> KSampler (pass 1, first 3-4 objects)
2. VAEDecode -> ImageToMask (isolate regions for remaining objects)
3. EmptySD3LatentImage -> KSampler (pass 2, remaining objects)
4. LatentComposite (merge pass 1 + pass 2)
5. VAEDecode -> SaveImage