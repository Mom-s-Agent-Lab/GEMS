# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed

**Skills — Anthropic Agent Skills specification**
- All 11 built-in skills now follow the [Agent Skills spec](https://agentskills.dev/specification):
  YAML frontmatter (`name`, `description`, optional `license`, `compatibility`,
  `allowed-tools`, `metadata`) followed by a plain Markdown instruction body.
- Skill directories renamed from `snake_case` to `kebab-case` to match the required
  `name` convention (`high_quality` → `high-quality`, `lora_enhancement` → `lora-enhancement`, etc.).
- `SkillManager` completely rewritten:
  - Parses YAML frontmatter with PyYAML; validates `name` matches directory name.
  - `build_available_skills_xml()` — generates the Anthropic-standard
    `<available_skills>` XML block (name + description + location only, stage 1).
  - `get_body(name)` — lazy-loads the full instruction body on demand (stage 2).
  - `detect_relevant_skills(prompt)` — keyword heuristic for hint suggestions.
  - `get_manifest()` — returns `list[{name, description, location}]`.
- `ClawAgent` updated for progressive disclosure:
  - System prompt now embeds the `<available_skills>` XML block at startup.
  - New **`read_skill`** tool (tool 14): agent calls this to load a skill's full
    instructions before applying the technique, rather than having all instructions
    injected up-front.
  - `_build_user_message` now only hints at relevant skill names; full bodies are
    never pre-loaded into the user message.
- Added `pyyaml>=6` runtime dependency.
- `test_skill_manager.py` fully rewritten: 43 tests covering frontmatter parsing,
  validation, XML generation, progressive disclosure, and edge cases.

---

## [0.1.0] — 2025-04-08

Initial public release extracted from the `vision-harness` research monorepo.

### Added

**Package structure**
- Standalone `comfyclaw/` Python package, installable via `pip` or `uv`.
- `pyproject.toml` with hatchling build backend, uv dependency groups, ruff/mypy config.
- `uv.lock` + `.python-version` (3.13) for reproducible environments.
- `.env.example` template covering all configuration variables.
- MIT `LICENSE`.

**Core modules**
- `client.py` — `ComfyClient`: HTTP REST + polling against the ComfyUI API.
- `workflow.py` — `WorkflowManager`: add / connect / delete / validate / clone nodes.
- `agent.py` — `ClawAgent`: Claude Sonnet tool-use loop with 14 tools for workflow evolution.
- `verifier.py` — `ClawVerifier`: Claude vision verifier with region-level analysis and configurable score weights.
- `memory.py` — `ClawMemory`: per-run attempt history with configurable image-bytes cap.
- `sync_server.py` — `SyncServer`: thread-safe WebSocket broadcast server.
- `skill_manager.py` — `SkillManager`: SKILL.md loader with YAML frontmatter parsing and progressive-disclosure XML generation.
- `harness.py` — `ClawHarness` + `HarnessConfig`: orchestrator with topology accumulation, early stopping, and context manager support.
- `cli.py` — `comfyclaw` CLI with `run`, `dry-run`, `install-node`, `node-path` sub-commands; reads all config from env vars / `.env`.

**Agent tools (14)**
`inspect_workflow`, `query_available_models`, `set_param`, `add_node`,
`connect_nodes`, `delete_node`, `add_lora_loader`, `add_controlnet`,
`add_regional_attention`, `add_hires_fix`, `add_inpaint_pass`,
`report_evolution_strategy`, `finalize_workflow`, `read_skill`.

**Built-in skills (11, Agent Skills format)**
`high-quality`, `photorealistic`, `creative`, `aesthetic-drawing`,
`lora-enhancement`, `controlnet-control`, `regional-control`, `hires-fix`,
`spatial`, `text-rendering`, `creative-drawing`.

**ComfyUI live-sync plugin**
- `comfyclaw/custom_node/` bundled inside the Python package.
- `comfy_claw_sync.js` v1.1: WebSocket client with auto-reconnect, three-method canvas reload (loadApiJson / loadGraphData / configure), status badge.
- Fixed: JS was reading `msg.data` but Python sends `msg.workflow`.
- `comfyclaw install-node` symlinks the bundled plugin; `comfyclaw node-path` prints its location.

**Tests** — 136 tests, fully offline (Anthropic mocked)
- `test_workflow.py` (23), `test_memory.py` (12), `test_skill_manager.py` (43),
  `test_verifier.py` (16), `test_agent.py` (17), `test_harness.py` (25).

### Fixed
- `WorkflowManager.delete_node`: added `str()` coerce for node-ID comparison.
- `ClawVerifier`: base64-encodes image bytes **once** before parallel threads (was re-encoding per question).
- `ClawVerifier`: detects JPEG vs PNG from magic bytes (was hardcoded `image/png`).
- `SkillManager`: now parses proper YAML frontmatter; old `get_instructions()` replaced by `get_body()`.
- `ClawAgent._add_regional_attention`: guards `node.get("_meta") or {}` to prevent `KeyError`.
- `SyncServer._clients`: protected with `threading.Lock` (was accessed unsafely across threads).
- `ClawHarness`: removed `sys.path.insert` hack; all imports within the package.

[Unreleased]: https://github.com/davidliuk/comfyclaw/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/davidliuk/comfyclaw/releases/tag/v0.1.0
