---
name: counting-objects
description: >-
  Enforce precise object counts (2-7 items) using regional conditioning for multi-type scenes, explicit numerical layout prompts, and count-specific negative prompts to override diffusion model tendency to generate 1 or 3 items.
license: MIT
metadata:
  cluster: "counting_multiple_objects"
  origin: "self-evolve"
---

# Counting Objects Skill

## When to Use
Trigger when the user specifies exact counts of objects (2-7 items), especially:
- Multiple instances of the same object: "five bears", "six cars", "four rabbits"
- Multiple different object types with counts: "a green backpack and a pig", "four rabbits and a sheep", "five bears and a donut"
- Any prompt containing number words (two, three, four, five, six, seven) or digits before nouns

## Core Problem
Diffusion models default to generating 1 or 3 objects regardless of prompt. When multiple DIFFERENT object types are specified, models often:
- Drop one object type entirely
- Merge characteristics of different objects
- Ignore counts and generate random numbers

## Solution Strategy

### For Single Object Type (e.g., "five bears")
1. Use explicit layout language: "five bears arranged in a row", "exactly 5 bears, counting from left to right"
2. Add count reinforcement to negative prompt: "1 bear, 2 bears, 3 bears, 4 bears, 6 bears, 7 bears"
3. Boost CFG to 8.5-9.5 for stronger prompt adherence
4. Increase steps to 35-40 for better convergence

### For Multiple Object Types (e.g., "a green backpack and a pig", "four rabbits and a sheep")
**CRITICAL**: When different object types appear together, use regional-control skill to:
1. Separate each object type into distinct spatial regions
2. Apply independent conditioning to each region
3. Prevent characteristic blending or object omission

Example regional split for "four rabbits and a sheep":
- Region 1 (left 60%): "exactly four rabbits, 4 rabbits in a group"
- Region 2 (right 40%): "one sheep, single sheep"

### Prompt Structure
- Lead with the count: "exactly [N] [objects]"
- Add spatial arrangement: "in a row", "in a circle", "spread across the scene"
- Emphasize counting: "counting all [N] items", "[N] total"
- Negative prompt: list wrong counts explicitly

### Node Configuration
- sampler_name: dpmpp_2m or euler
- scheduler: karras
- steps: 35-40 (higher for better count accuracy)
- cfg: 8.5-9.5 (stronger guidance)
- Use regional conditioning nodes when multiple object types present

## Execution Checklist
1. Parse prompt for object counts and types
2. If multiple different object types → invoke regional-control skill
3. Restructure prompt with explicit count language
4. Add wrong-count terms to negative prompt
5. Raise CFG and steps
6. Verify output has correct count before returning