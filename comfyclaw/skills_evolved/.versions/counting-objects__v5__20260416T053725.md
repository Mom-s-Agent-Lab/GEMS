---
name: counting-objects
description: >-
  Enforce precise object counts (2-7 items) using count repetition syntax, explicit numerical negatives, and regional conditioning fallback to override diffusion model's tendency toward single or triplet generation.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects

## When to Use
Trigger when the prompt contains explicit quantities: "two", "three", "four", "five", "six", "seven", "2", "3", "4", "5", "6", "7", "a pair of", "a trio of", "several", or when the verifier reports wrong object count.

## Core Strategy
Diffusion models collapse to 1 or 3 objects unless forced. Use three enforcement layers:

### 1. Repetition Syntax (counts 2-4)
Repeat the object name exactly N times in the positive prompt:
- "two cats" → "cat, cat, two cats"
- "three monkeys" → "monkey, monkey, monkey, three brown monkeys"
- "four zebras" → "zebra, zebra, zebra, zebra, four metal zebras"

### 2. Explicit Count Negatives
Add to negative prompt: "one [object], single [object], solo, alone" for count=2, and "pair, duo" for count≥3.

### 3. Regional Fallback (counts ≥3)
For 3+ objects AND when first attempt fails:
- Call regional-control skill
- Divide canvas into N equal regions (horizontal or grid)
- Assign one object per region with identical descriptor
- Use RegionalConditioningSimple or attention masking

### 4. Layout Hints
Add arrangement terms: "arranged in a row", "lined up", "group of N", "cluster of N", "N identical [objects]"

## Implementation
1. Detect count from prompt (regex: "(two|three|four|2|3|4) (\w+)")
2. Restructure positive prompt with repetition + layout
3. Inject count-specific negatives
4. If count ≥3 and regional-control is available, build regional conditioning nodes
5. Use CFG 7-9 (higher CFG enforces count better)
6. Steps ≥25 for count convergence

## Example Transforms
- "two stone raccoons" → "stone raccoon, stone raccoon, two stone raccoons arranged side by side | negative: one raccoon, single raccoon, solo"
- "four brown monkeys" → [trigger regional-control with 4 horizontal regions, each conditioned on "brown monkey"]

## Failure Recovery
If output still has wrong count: increase CFG to 10, add "exactly N" prefix, or switch to pure regional conditioning with explicit grid layout.