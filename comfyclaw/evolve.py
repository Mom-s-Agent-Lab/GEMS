"""
SkillEvolver — Self-evolution engine for ComfyClaw's skill system.

Runs benchmark batches, clusters failure patterns, proposes skill mutations
(create/update/merge/delete), validates on a held-out set, and commits or
rolls back based on score improvement.

Usage::

    evolver = SkillEvolver(skills_dir="skills/", benchmark_config=cfg)
    report = evolver.run_cycle(train_prompts, val_prompts)
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import litellm

from .skill_manager import SkillManager
from .skill_store import SkillStore

log = logging.getLogger(__name__)


# ── Data types ─────────────────────────────────────────────────────────────


@dataclass
class FailureCluster:
    """A group of related failures across benchmark prompts."""

    name: str
    description: str
    failure_count: int
    affected_prompts: list[str]
    mean_score: float
    example_feedback: list[str]
    existing_skill: str | None = None


@dataclass
class MutationProposal:
    """A proposed change to the skill set."""

    mutation_type: str  # create | update | merge | delete
    target_skills: list[str]
    rationale: str
    failure_cluster: str
    proposed_changes: dict[str, str] = field(default_factory=dict)
    pre_score: float = 0.0
    post_score: float | None = None
    accepted: bool = False


@dataclass
class EvolutionReport:
    """Summary of one evolution cycle."""

    cycle: int
    pre_mean_score: float
    post_mean_score: float
    mutations_proposed: int
    mutations_accepted: int
    mutations_rejected: int
    failure_clusters: list[FailureCluster]
    mutations: list[MutationProposal]
    duration_s: float = 0.0

    def summary(self) -> str:
        delta = self.post_mean_score - self.pre_mean_score
        sign = "+" if delta >= 0 else ""
        return (
            f"Cycle {self.cycle}: score {self.pre_mean_score:.4f} -> "
            f"{self.post_mean_score:.4f} ({sign}{delta:.4f})\n"
            f"  Clusters: {len(self.failure_clusters)}\n"
            f"  Mutations: {self.mutations_proposed} proposed, "
            f"{self.mutations_accepted} accepted, "
            f"{self.mutations_rejected} rejected\n"
            f"  Duration: {self.duration_s:.1f}s"
        )


# ── Prompts for LLM-driven analysis ───────────────────────────────────────

_CLUSTER_FAILURES_PROMPT = """\
You are an expert at analyzing image generation failures. Given the following
benchmark results (prompt, score, verifier feedback), cluster the failures
into categories.

Results:
{results_json}

Available skills: {skill_names}

Return a JSON array of failure clusters:
[
  {{
    "name": "cluster_name",
    "description": "What characterizes this failure pattern",
    "prompt_indices": [0, 3, 7],
    "existing_skill": "skill-name or null if no skill covers this"
  }}
]

Focus on actionable clusters where a skill could help. Ignore one-off failures.
"""

_PROPOSE_MUTATION_PROMPT = """\
You are a skill evolution engine. Given this failure cluster and the current
skill set, propose a skill mutation to address the failures.

Failure cluster: {cluster_json}

Current skills and their descriptions:
{skills_manifest}

Mutation types:
- "create": New skill for an uncovered failure pattern
- "update": Improve an existing skill's instructions
- "merge": Combine overlapping skills
- "delete": Remove a skill that is not helping

Return a JSON object:
{{
  "mutation_type": "create|update|merge|delete",
  "target_skills": ["skill-name"],
  "rationale": "Why this mutation addresses the cluster",
  "proposed_changes": {{
    "name": "skill-name",
    "description": "Skill description for frontmatter",
    "body": "Full SKILL.md body with instructions"
  }}
}}

For "update", provide the improved body text.
For "merge", provide the merged skill content.
For "delete", target_skills lists which to remove; proposed_changes can be empty.
"""


# ── SkillEvolver ───────────────────────────────────────────────────────────


class SkillEvolver:
    """Autonomous skill evolution engine.

    Parameters
    ----------
    skills_dir : Path to the skills directory.
    llm_model  : LLM for failure analysis and mutation proposal.
    api_key    : API key for the LLM provider.
    min_improvement : Minimum score improvement to accept a mutation.
    max_mutations_per_cycle : Maximum mutations to attempt per cycle.
    """

    def __init__(
        self,
        skills_dir: str | Path,
        llm_model: str = "anthropic/claude-sonnet-4-5",
        api_key: str = "",
        min_improvement: float = 0.02,
        max_mutations_per_cycle: int = 3,
    ) -> None:
        self.skills_dir = Path(skills_dir)
        self.store = SkillStore(self.skills_dir)
        self.skill_manager = SkillManager(str(self.skills_dir))
        self.llm_model = llm_model
        self.api_key = api_key
        self.min_improvement = min_improvement
        self.max_mutations_per_cycle = max_mutations_per_cycle

        if api_key:
            os.environ.setdefault("ANTHROPIC_API_KEY", api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_cycle(
        self,
        results: list[dict[str, Any]],
        run_validation_fn: Any | None = None,
        cycle: int = 1,
    ) -> EvolutionReport:
        """Execute one evolution cycle.

        Parameters
        ----------
        results : List of dicts with keys ``prompt``, ``score``, ``feedback``,
                  ``passed``, ``failed`` from a benchmark run.
        run_validation_fn : Optional callable that re-runs benchmark and
                           returns mean score.  Signature: ``() -> float``.
        cycle : Cycle number for logging.

        Returns
        -------
        EvolutionReport summarising what happened.
        """
        t0 = time.time()
        pre_mean = self._mean_score(results)
        log.info("Cycle %d: pre-evolution mean score = %.4f", cycle, pre_mean)

        # Step 1: Cluster failures
        failures = [r for r in results if r.get("score", 0) < 0.7]
        if not failures:
            log.info("No significant failures to address (all scores >= 0.7)")
            return EvolutionReport(
                cycle=cycle,
                pre_mean_score=pre_mean,
                post_mean_score=pre_mean,
                mutations_proposed=0,
                mutations_accepted=0,
                mutations_rejected=0,
                failure_clusters=[],
                mutations=[],
                duration_s=time.time() - t0,
            )

        clusters = self._cluster_failures(failures)
        log.info("Found %d failure clusters", len(clusters))

        # Step 2: Propose mutations
        mutations: list[MutationProposal] = []
        for cluster in clusters[: self.max_mutations_per_cycle]:
            proposal = self._propose_mutation(cluster)
            if proposal:
                proposal.pre_score = pre_mean
                mutations.append(proposal)

        # Step 3: Apply and validate each mutation
        accepted = 0
        rejected = 0
        post_mean = pre_mean

        for mutation in mutations:
            log.info(
                "Applying mutation: %s on %s",
                mutation.mutation_type,
                mutation.target_skills,
            )
            try:
                self._apply_mutation(mutation)

                if run_validation_fn:
                    val_score = run_validation_fn()
                    mutation.post_score = val_score
                    improvement = val_score - pre_mean

                    if improvement >= self.min_improvement:
                        mutation.accepted = True
                        accepted += 1
                        post_mean = val_score
                        log.info(
                            "Mutation accepted: +%.4f (%.4f -> %.4f)",
                            improvement, pre_mean, val_score,
                        )
                        # Reload skill manager to pick up changes
                        self.skill_manager = SkillManager(str(self.skills_dir))
                    else:
                        self._rollback_mutation(mutation)
                        rejected += 1
                        log.info(
                            "Mutation rejected: improvement %.4f < threshold %.4f",
                            improvement, self.min_improvement,
                        )
                else:
                    # No validation function — accept optimistically
                    mutation.accepted = True
                    accepted += 1
                    self.skill_manager = SkillManager(str(self.skills_dir))

            except Exception as exc:
                log.error("Mutation failed: %s", exc)
                rejected += 1

        return EvolutionReport(
            cycle=cycle,
            pre_mean_score=pre_mean,
            post_mean_score=post_mean,
            mutations_proposed=len(mutations),
            mutations_accepted=accepted,
            mutations_rejected=rejected,
            failure_clusters=clusters,
            mutations=mutations,
            duration_s=time.time() - t0,
        )

    def run_multi_cycle(
        self,
        results: list[dict[str, Any]],
        run_validation_fn: Any | None = None,
        max_cycles: int = 10,
        convergence_threshold: float = 0.01,
    ) -> list[EvolutionReport]:
        """Run multiple evolution cycles until convergence."""
        reports: list[EvolutionReport] = []
        recent_improvements: list[float] = []

        for cycle in range(1, max_cycles + 1):
            report = self.run_cycle(results, run_validation_fn, cycle=cycle)
            reports.append(report)
            log.info(report.summary())

            delta = report.post_mean_score - report.pre_mean_score
            recent_improvements.append(delta)

            # Check convergence: avg improvement over last 3 cycles
            if len(recent_improvements) >= 3:
                avg_recent = sum(recent_improvements[-3:]) / 3
                if avg_recent < convergence_threshold:
                    log.info(
                        "Converged: avg improvement %.4f < threshold %.4f",
                        avg_recent, convergence_threshold,
                    )
                    break

            if report.mutations_accepted == 0 and report.mutations_proposed > 0:
                log.info("No mutations accepted this cycle — stopping early.")
                break

        return reports

    # ------------------------------------------------------------------
    # Private: failure clustering
    # ------------------------------------------------------------------

    def _cluster_failures(self, failures: list[dict]) -> list[FailureCluster]:
        """Use the LLM to cluster failures by pattern."""
        results_for_llm = []
        for i, f in enumerate(failures[:30]):
            results_for_llm.append({
                "index": i,
                "prompt": f.get("prompt", ""),
                "score": f.get("score", 0),
                "failed_requirements": f.get("failed", [])[:5],
                "feedback_snippet": str(f.get("feedback", ""))[:200],
            })

        skill_names = ", ".join(self.store.list_skills())

        prompt = _CLUSTER_FAILURES_PROMPT.format(
            results_json=json.dumps(results_for_llm, indent=2),
            skill_names=skill_names or "(none)",
        )

        try:
            resp = litellm.completion(
                model=self.llm_model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            text = (resp.choices[0].message.content or "").strip()
            m = re.search(r"\[.*\]", text, re.DOTALL)
            raw_clusters = json.loads(m.group() if m else text)
        except Exception as exc:
            log.error("Failure clustering failed: %s", exc)
            return []

        clusters: list[FailureCluster] = []
        for rc in raw_clusters:
            indices = rc.get("prompt_indices", [])
            affected = [
                failures[i]["prompt"]
                for i in indices
                if i < len(failures)
            ]
            scores = [
                failures[i].get("score", 0)
                for i in indices
                if i < len(failures)
            ]
            feedback = [
                str(failures[i].get("feedback", ""))[:100]
                for i in indices[:3]
                if i < len(failures)
            ]

            clusters.append(FailureCluster(
                name=rc.get("name", "unknown"),
                description=rc.get("description", ""),
                failure_count=len(indices),
                affected_prompts=affected,
                mean_score=sum(scores) / len(scores) if scores else 0.0,
                example_feedback=feedback,
                existing_skill=rc.get("existing_skill"),
            ))

        # Sort by failure count (most impactful first)
        clusters.sort(key=lambda c: c.failure_count, reverse=True)
        return clusters

    # ------------------------------------------------------------------
    # Private: mutation proposal
    # ------------------------------------------------------------------

    def _propose_mutation(self, cluster: FailureCluster) -> MutationProposal | None:
        """Ask the LLM to propose a skill mutation for a failure cluster."""
        manifest = "\n".join(
            f"- {s['name']}: {s['description']}"
            for s in self.skill_manager.get_manifest()
        )

        cluster_json = json.dumps({
            "name": cluster.name,
            "description": cluster.description,
            "failure_count": cluster.failure_count,
            "mean_score": cluster.mean_score,
            "example_feedback": cluster.example_feedback,
            "existing_skill": cluster.existing_skill,
            "affected_prompts": cluster.affected_prompts[:5],
        }, indent=2)

        prompt = _PROPOSE_MUTATION_PROMPT.format(
            cluster_json=cluster_json,
            skills_manifest=manifest or "(no skills)",
        )

        try:
            resp = litellm.completion(
                model=self.llm_model,
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = (resp.choices[0].message.content or "").strip()
            m = re.search(r"\{.*\}", text, re.DOTALL)
            data = json.loads(m.group() if m else text)
        except Exception as exc:
            log.error("Mutation proposal failed for cluster %s: %s", cluster.name, exc)
            return None

        return MutationProposal(
            mutation_type=data.get("mutation_type", "update"),
            target_skills=data.get("target_skills", []),
            rationale=data.get("rationale", ""),
            failure_cluster=cluster.name,
            proposed_changes=data.get("proposed_changes", {}),
        )

    # ------------------------------------------------------------------
    # Private: apply / rollback mutations
    # ------------------------------------------------------------------

    def _apply_mutation(self, mutation: MutationProposal) -> None:
        """Apply a mutation to the skill store."""
        changes = mutation.proposed_changes
        mt = mutation.mutation_type

        if mt == "create":
            self.store.create_skill(
                name=changes.get("name", f"auto-{mutation.failure_cluster}"),
                description=changes.get("description", "Auto-generated skill"),
                body=changes.get("body", ""),
                metadata={"origin": "self-evolve", "cluster": mutation.failure_cluster},
            )

        elif mt == "update":
            for skill_name in mutation.target_skills:
                self.store.update_skill(
                    name=skill_name,
                    description=changes.get("description"),
                    body=changes.get("body"),
                )

        elif mt == "merge":
            self.store.merge_skills(
                names=mutation.target_skills,
                merged_name=changes.get("name", mutation.target_skills[0]),
                merged_description=changes.get("description", "Merged skill"),
                merged_body=changes.get("body", ""),
                delete_originals=True,
            )

        elif mt == "delete":
            for skill_name in mutation.target_skills:
                self.store.delete_skill(skill_name)

        else:
            raise ValueError(f"Unknown mutation type: {mt}")

    def _rollback_mutation(self, mutation: MutationProposal) -> None:
        """Rollback a mutation by restoring from the latest snapshot."""
        mt = mutation.mutation_type

        if mt == "create":
            name = mutation.proposed_changes.get(
                "name", f"auto-{mutation.failure_cluster}"
            )
            try:
                self.store.delete_skill(name)
            except FileNotFoundError:
                pass

        elif mt == "update":
            for skill_name in mutation.target_skills:
                try:
                    self.store.rollback_skill(skill_name)
                except FileNotFoundError:
                    pass

        elif mt == "merge":
            # Restore originals from snapshots
            for skill_name in mutation.target_skills:
                try:
                    self.store.rollback_skill(skill_name)
                except FileNotFoundError:
                    pass
            merged = mutation.proposed_changes.get("name")
            if merged and merged not in mutation.target_skills:
                try:
                    self.store.delete_skill(merged)
                except FileNotFoundError:
                    pass

        elif mt == "delete":
            for skill_name in mutation.target_skills:
                try:
                    self.store.rollback_skill(skill_name)
                except FileNotFoundError:
                    pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mean_score(results: list[dict]) -> float:
        scores = [r.get("score", 0.0) for r in results]
        return sum(scores) / len(scores) if scores else 0.0
