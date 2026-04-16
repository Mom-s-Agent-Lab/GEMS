import os
import re


class SkillManager:
    """Parses SKILL.md files from a skills directory.

    Supports two on-disk formats:

    1. Legacy GEMS format
       ----------------
       # Skill: <Name>
       ## Description
       <description>
       ## Instructions
       <instructions>

    2. Agent-Skills YAML-frontmatter format (used by comfyclaw and others)
       ----------------
       ---
       name: <kebab-case-id>
       description: <one-liner or YAML block scalar>
       ...
       ---
       <body, treated as instructions>

    The SKILL_ID surfaced to the planner is always the folder name.
    """

    def __init__(self, skills_dir="agent/skills"):
        self.skills_dir = skills_dir
        self.skills = self._load_skills()

    def _load_skills(self):
        skills_data = {}
        if not os.path.exists(self.skills_dir):
            return {}

        for skill_id in sorted(os.listdir(self.skills_dir)):
            md_path = os.path.join(self.skills_dir, skill_id, "SKILL.md")
            if not os.path.exists(md_path):
                md_path = os.path.join(self.skills_dir, skill_id, "skill.md")
            if not os.path.exists(md_path):
                continue

            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()

            parsed = self._parse_skill_file(content)
            if parsed is None:
                continue

            description, instructions = parsed
            skills_data[skill_id] = {
                "id": skill_id,
                "description": description,
                "instructions": instructions,
            }
        return skills_data

    @staticmethod
    def _parse_skill_file(content: str):
        """Return (description, instructions) parsed from either supported format."""
        stripped = content.lstrip()
        if stripped.startswith("---"):
            desc, body = SkillManager._parse_frontmatter(stripped)
            if desc is None and not body:
                return None
            return desc or "", body or ""

        desc_match = re.search(r"## Description\s*\n(.*?)\n##", content, re.DOTALL)
        instr_match = re.search(r"## Instructions\s*\n(.*)", content, re.DOTALL)
        description = desc_match.group(1).strip() if desc_match else ""
        instructions = instr_match.group(1).strip() if instr_match else ""
        if not description and not instructions:
            return None
        return description, instructions

    @staticmethod
    def _parse_frontmatter(content: str):
        """Extract description + body from an Agent-Skills frontmatter file.

        Pure-regex (no PyYAML dependency) — we only need the ``description``
        field; everything after the closing ``---`` becomes the instructions.
        """
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None, ""
        _, frontmatter, body = parts
        body = body.lstrip("\n")

        desc_match = re.search(
            r"^description\s*:\s*(>-?|>|\|-?|\|)?\s*\n((?:[ \t]+.*\n?)+)",
            frontmatter,
            re.MULTILINE,
        )
        if desc_match:
            raw_block = desc_match.group(2)
            lines = [ln.strip() for ln in raw_block.splitlines() if ln.strip()]
            description = " ".join(lines)
        else:
            single = re.search(
                r"^description\s*:\s*(.+?)\s*$", frontmatter, re.MULTILINE
            )
            description = single.group(1).strip() if single else ""
            description = description.strip('"').strip("'")

        return description, body.strip()

    def get_skill_manifest(self):
        manifest = ""
        for s_id, data in self.skills.items():
            manifest += f"- SKILL_ID: {s_id}\n  DESCRIPTION: {data['description']}\n"
        return manifest
