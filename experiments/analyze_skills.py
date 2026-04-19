#!/usr/bin/env python3
"""
Analyze evolved skill impact on benchmark performance.

Reads results.json and (optionally) SFT traces to determine:
  - Which evolved skills were read per prompt
  - Score comparison: prompts WITH vs WITHOUT evolved skills
  - Per-skill usage frequency and average score when used
  - Which evolved skills are never read (candidates for pruning)

Supports two data sources for skill usage:
  1. The `skills_read` field in results.json (preferred, added by the tracking patch)
  2. Fallback: parsing `sft_traces.jsonl` for `read_skill` tool calls (legacy results)

Usage:
    python experiments/analyze_skills.py \\
        --results path/to/results.json \\
        --evolved-dir path/to/evolved_skills/ \\
        [--detailed-dir path/to/detailed/]   # needed for SFT fallback
"""
import argparse
import glob
import json
import logging
import os
import sys
from collections import Counter
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("analyze_skills")


def _load_results(results_path: str) -> list[dict]:
    with open(results_path, encoding="utf-8") as f:
        return json.load(f)


def _discover_evolved_skills(evolved_dir: str) -> set[str]:
    """Return the set of evolved skill names (directory names under evolved_dir)."""
    skills = set()
    if not os.path.isdir(evolved_dir):
        return skills
    for name in os.listdir(evolved_dir):
        path = os.path.join(evolved_dir, name)
        if os.path.isdir(path) and name != ".versions":
            skills.add(name)
    return skills


def _extract_skills_from_traces(prompt_dir: str) -> set[str]:
    """Parse sft_traces.jsonl in a prompt directory for read_skill calls."""
    trace_file = os.path.join(prompt_dir, "sft_traces.jsonl")
    skills = set()
    if not os.path.exists(trace_file):
        return skills
    with open(trace_file, encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
                for msg in d.get("messages", []):
                    if isinstance(msg.get("tool_calls"), list):
                        for tc in msg["tool_calls"]:
                            if tc.get("function", {}).get("name") == "read_skill":
                                args = json.loads(tc["function"]["arguments"])
                                skills.add(args.get("skill_name", ""))
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
    return skills


def _get_skills_for_result(
    result: dict,
    detailed_dir: str | None,
) -> list[str]:
    """Get skills read for a result, using skills_read field or SFT fallback."""
    if "skills_read" in result and result["skills_read"]:
        return result["skills_read"]

    if not detailed_dir:
        return []

    idx = result["idx"]
    slug_dirs = glob.glob(os.path.join(detailed_dir, f"prompt_{idx}_*"))
    if not slug_dirs:
        return []

    return sorted(_extract_skills_from_traces(slug_dirs[0]))


def _load_version_timestamps(evolved_dir: str) -> dict[str, str]:
    """Load skill creation timestamps from .versions/ directory."""
    versions_dir = os.path.join(evolved_dir, ".versions")
    timestamps = {}
    if not os.path.isdir(versions_dir):
        return timestamps
    for fname in os.listdir(versions_dir):
        parts = fname.replace(".md", "").split("__")
        if len(parts) >= 3:
            skill_name = parts[0]
            timestamp = parts[2]
            if skill_name not in timestamps:
                timestamps[skill_name] = timestamp
    return timestamps


def _load_evolution_reports(evolved_dir: str) -> list[dict]:
    """Load persisted evolution reports if available."""
    report_path = os.path.join(evolved_dir, "evolution_reports.jsonl")
    reports = []
    if not os.path.exists(report_path):
        return reports
    with open(report_path, encoding="utf-8") as f:
        for line in f:
            try:
                reports.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return reports


def analyze(
    results: list[dict],
    evolved_skill_names: set[str],
    detailed_dir: str | None,
    evolved_dir: str,
) -> None:
    """Run the full analysis and print a report."""

    # ── Enrich results with skills data ───────────────────────────────
    data_source = "skills_read field"
    has_skills_field = any("skills_read" in r for r in results)
    if not has_skills_field:
        if detailed_dir:
            data_source = "SFT trace parsing (legacy fallback)"
        else:
            log.warning(
                "No skills_read field in results and no --detailed-dir provided. "
                "Cannot determine skill usage."
            )
            return

    enriched = []
    for r in results:
        skills = _get_skills_for_result(r, detailed_dir)
        evolved_used = [s for s in skills if s in evolved_skill_names]
        enriched.append({
            **r,
            "_skills": skills,
            "_evolved_used": evolved_used,
            "_has_evolved": len(evolved_used) > 0,
        })

    n_total = len(enriched)
    n_with_traces = sum(1 for e in enriched if e["_skills"])

    # ── Header ────────────────────────────────────────────────────────
    log.info("=" * 70)
    log.info("SKILL IMPACT ANALYSIS")
    log.info("=" * 70)
    log.info("Data source:       %s", data_source)
    log.info("Total prompts:     %d", n_total)
    log.info("With skill data:   %d", n_with_traces)
    log.info("Evolved skills:    %d", len(evolved_skill_names))
    log.info("")

    if n_with_traces == 0:
        log.warning("No skill usage data found. Nothing to analyze.")
        return

    # ── Overall skill usage ───────────────────────────────────────────
    all_skills: Counter[str] = Counter()
    for e in enriched:
        for s in e["_skills"]:
            all_skills[s] += 1

    log.info("── All skills read (top 20) ──")
    log.info("%-40s  %5s  %s", "Skill", "Count", "Type")
    log.info("-" * 60)
    for skill, count in all_skills.most_common(20):
        stype = "EVOLVED" if skill in evolved_skill_names else "built-in"
        log.info("%-40s  %5d  %s", skill, count, stype)
    log.info("")

    # ── Evolved skill impact: WITH vs WITHOUT ─────────────────────────
    with_evolved = [e for e in enriched if e["_has_evolved"]]
    without_evolved = [e for e in enriched if not e["_has_evolved"] and e["_skills"]]

    log.info("── Evolved skill impact ──")
    log.info("")

    if not with_evolved:
        log.info("No prompts used an evolved skill.")
    else:
        _print_group_comparison(with_evolved, without_evolved)

    log.info("")

    # ── Per evolved skill breakdown ───────────────────────────────────
    evolved_usage: Counter[str] = Counter()
    evolved_scores: dict[str, list[float]] = {}
    evolved_baselines: dict[str, list[float]] = {}
    evolved_deltas: dict[str, list[float]] = {}

    for e in enriched:
        for s in e["_evolved_used"]:
            evolved_usage[s] += 1
            evolved_scores.setdefault(s, []).append(e["best_score"])
            evolved_baselines.setdefault(s, []).append(e.get("baseline_score", 0))
            evolved_deltas.setdefault(s, []).append(
                e["best_score"] - e.get("baseline_score", 0)
            )

    if evolved_usage:
        log.info("── Per evolved skill report card ──")
        log.info("")
        log.info(
            "%-40s  %5s  %8s  %8s  %8s",
            "Skill", "Used", "AvgBase", "AvgBest", "AvgDelta",
        )
        log.info("-" * 75)

        overall_avg = (
            sum(e["best_score"] for e in enriched) / n_total if n_total else 0
        )

        for skill, count in evolved_usage.most_common():
            avg_best = sum(evolved_scores[skill]) / count
            avg_base = sum(evolved_baselines[skill]) / count
            avg_delta = sum(evolved_deltas[skill]) / count
            marker = " ▲" if avg_best > overall_avg else " ▼"
            log.info(
                "%-40s  %5d  %8.4f  %8.4f  %+8.4f%s",
                skill, count, avg_base, avg_best, avg_delta, marker,
            )
        log.info("")
        log.info("  ▲ = above overall avg (%.4f)   ▼ = below overall avg", overall_avg)

    log.info("")

    # ── Never-read evolved skills ─────────────────────────────────────
    never_read = evolved_skill_names - set(evolved_usage.keys())
    if never_read:
        log.info("── Evolved skills NEVER read (%d/%d) ──", len(never_read), len(evolved_skill_names))
        log.info("  These skills were created but never used by the agent:")
        for s in sorted(never_read):
            log.info("    - %s", s)
        log.info("")

    # ── Evolution reports timeline ────────────────────────────────────
    reports = _load_evolution_reports(evolved_dir)
    if reports:
        log.info("── Evolution cycle history ──")
        log.info("")
        log.info(
            "%5s  %8s  %8s  %8s  %5s  %5s  %5s",
            "Cycle", "PreScore", "PostScore", "Delta", "Prop", "Acc", "Rej",
        )
        log.info("-" * 55)
        for rep in reports:
            delta = rep["post_mean_score"] - rep["pre_mean_score"]
            log.info(
                "%5d  %8.4f  %8.4f  %+8.4f  %5d  %5d  %5d",
                rep["cycle"],
                rep["pre_mean_score"],
                rep["post_mean_score"],
                delta,
                rep["mutations_proposed"],
                rep["mutations_accepted"],
                rep["mutations_rejected"],
            )
        log.info("")

    # ── Skill creation timeline ───────────────────────────────────────
    timestamps = _load_version_timestamps(evolved_dir)
    if timestamps:
        log.info("── Skill creation timeline ──")
        for skill, ts in sorted(timestamps.items(), key=lambda x: x[1]):
            used = evolved_usage.get(skill, 0)
            log.info("  %s  %-40s  used %dx", ts, skill, used)
        log.info("")


def _print_group_comparison(
    with_evolved: list[dict],
    without_evolved: list[dict],
) -> None:
    """Print a comparison table of prompts with vs without evolved skills."""
    def _stats(group: list[dict]) -> tuple[int, float, float, float]:
        n = len(group)
        if n == 0:
            return 0, 0.0, 0.0, 0.0
        avg_base = sum(e.get("baseline_score", 0) for e in group) / n
        avg_best = sum(e["best_score"] for e in group) / n
        avg_delta = sum(e["best_score"] - e.get("baseline_score", 0) for e in group) / n
        return n, avg_base, avg_best, avg_delta

    log.info(
        "%-30s  %5s  %8s  %8s  %8s",
        "Group", "N", "AvgBase", "AvgBest", "AvgDelta",
    )
    log.info("-" * 65)

    n, avg_b, avg_s, avg_d = _stats(with_evolved)
    log.info("%-30s  %5d  %8.4f  %8.4f  %+8.4f", "WITH evolved skill", n, avg_b, avg_s, avg_d)

    n, avg_b, avg_s, avg_d = _stats(without_evolved)
    log.info("%-30s  %5d  %8.4f  %8.4f  %+8.4f", "WITHOUT evolved skill", n, avg_b, avg_s, avg_d)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze evolved skill impact on benchmark performance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--results", required=True,
        help="Path to results.json",
    )
    parser.add_argument(
        "--evolved-dir", required=True,
        help="Path to evolved_skills directory (e.g. comfyclaw/evolved_skills/longcat_geneval2/claude-sonnet-4-5)",
    )
    parser.add_argument(
        "--detailed-dir", default=None,
        help="Path to detailed results directory (for SFT trace fallback when skills_read is missing)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.results):
        log.error("Results file not found: %s", args.results)
        sys.exit(1)
    if not os.path.isdir(args.evolved_dir):
        log.error("Evolved skills directory not found: %s", args.evolved_dir)
        sys.exit(1)

    results = _load_results(args.results)
    evolved_skill_names = _discover_evolved_skills(args.evolved_dir)

    if not evolved_skill_names:
        log.info("No evolved skills found in %s", args.evolved_dir)
        sys.exit(0)

    analyze(results, evolved_skill_names, args.detailed_dir, args.evolved_dir)


if __name__ == "__main__":
    main()
