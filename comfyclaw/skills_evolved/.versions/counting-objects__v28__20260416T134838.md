---
name: counting-objects
description: >-
  Enforce accurate object counts (2-7+) through mandatory regional-control integration, explicit spatial grid layouts with position tokens, and per-instance attention emphasis. MUST combine with unusual-attributes for non-standard colors/materials.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

## When to Use
Trigger when the prompt contains explicit counts: "two cats", "three zebras", "four rabbits", "five birds", etc. Also trigger for implicit counts like "a pair of", "trio of", or "several" with context clues.

## Critical Rules for Medium Counts (3-4 objects)
This range has the highest failure rate. Apply ALL of the following:

1. **Mandatory Regional Control Integration**
   - ALWAYS invoke regional-control skill for counts ≥3
   - Never rely on base prompt alone for 3+ objects
   - Each object must get its own isolated regional prompt

2. **Explicit Grid Layout**
   - For 3 objects: Use "arranged in a triangle", "left, center, right"
   - For 4 objects: Use "in a 2x2 grid", "in a square formation", "evenly spaced in a row"
   - Add spatial position tokens: "first", "second", "third", "fourth"

3. **Per-Instance Differentiation**
   - Give each object a subtle unique attribute: "first rabbit with white paws", "second rabbit with grey ears", "third rabbit with brown tail", "fourth rabbit with black nose"
   - This prevents model collapse where multiple instances fuse into one

4. **Rewrite Pattern for 3-4 Objects**
   ```
   Original: "four brown monkeys"
   Rewritten: "four distinct brown monkeys arranged in a square formation: (first monkey with lighter face:1.2) in top-left, (second monkey with darker hands:1.2) in top-right, (third monkey with bushy tail:1.2) in bottom-left, (fourth monkey with white chest:1.2) in bottom-right, evenly spaced, full bodies visible, separated"
   ```

5. **Emphasis Syntax**
   - Wrap count in strong emphasis: "(exactly four:1.4)", "(three separate:1.3)"
   - Add negative prompt: "merged, fused, overlapping, single, combined, less than [N], more than [N]"

6. **Fusion Prevention**
   - Add "well-separated", "distinct individuals", "clear gaps between", "non-overlapping"
   - Increase CFG slightly (0.5-1.0 higher) to strengthen text adherence

## Node-Level Implementation
1. Call regional-control skill to set up region conditioning
2. Modify base prompt with grid layout + emphasis + fusion-prevention terms
3. Add count-specific negative prompt tokens
4. If unusual attributes present (colors/materials), call unusual-attributes skill AFTER applying count structure

## Validation
Before finalizing, check prompt contains:
- Explicit count with emphasis: "(exactly N:1.3+)"
- Spatial arrangement description
- Per-instance differentiators
- Fusion-prevention language
- Regional conditioning setup (for N≥3)