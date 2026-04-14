"""
BenchmarkRunner — drives ComfyClaw on standardised prompt sets.

Each benchmark adapter yields ``(index, prompt, metadata)`` tuples.
The runner feeds each prompt through ``ClawHarness.run()``, saves the
resulting image, and collects metrics (verifier score, latency, node count).
"""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run."""

    suite: str  # geneval2 | crea | oneig
    name: str  # experiment name (output subfolder)
    data_path: str  # path to benchmark data file
    output_dir: str = "benchmark_results"
    max_iterations: int = 3  # per-prompt ClawHarness iterations
    num_workers: int = 1  # parallel workers
    server_address: str = "127.0.0.1:8188"
    api_key: str = ""
    model: str = "anthropic/claude-sonnet-4-5"
    image_model: str | None = None
    workflow_path: str | None = None  # base workflow JSON
    stage_gated: bool = False
    verifier_model: str | None = None
    max_prompts: int | None = None  # limit for quick testing


@dataclass
class BenchmarkResult:
    """Aggregated results from a benchmark run."""

    suite: str
    name: str
    total_prompts: int
    completed: int
    failed: int
    mean_score: float
    scores: list[float]
    mean_latency_s: float
    per_prompt: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            f"Benchmark: {self.suite} / {self.name}",
            f"Prompts: {self.completed}/{self.total_prompts} completed, "
            f"{self.failed} failed",
            f"Mean score: {self.mean_score:.4f}",
            f"Mean latency: {self.mean_latency_s:.1f}s",
        ]
        if self.metrics:
            lines.append("Metrics:")
            for k, v in sorted(self.metrics.items()):
                lines.append(f"  {k}: {v:.4f}")
        return "\n".join(lines)


def _run_single_prompt(
    idx: int,
    prompt: str,
    metadata: dict,
    output_dir: str,
    harness_kwargs: dict,
) -> dict[str, Any]:
    """Worker function: run one prompt through ClawHarness and save results."""
    from ..harness import ClawHarness, HarnessConfig

    cfg = HarnessConfig(**harness_kwargs)
    result: dict[str, Any] = {
        "index": idx,
        "prompt": prompt,
        "metadata": metadata,
        "score": 0.0,
        "latency_s": 0.0,
        "error": None,
        "image_path": None,
        "node_count": 0,
    }

    try:
        if harness_kwargs.get("_workflow_path"):
            harness = ClawHarness.from_workflow_file(
                harness_kwargs["_workflow_path"], cfg
            )
        else:
            harness = ClawHarness.from_workflow_dict({}, cfg)

        with harness:
            t0 = time.time()
            image_bytes = harness.run(prompt)
            result["latency_s"] = time.time() - t0

            if image_bytes:
                img_name = f"img_{idx:05d}.png"
                img_path = os.path.join(output_dir, img_name)
                with open(img_path, "wb") as f:
                    f.write(image_bytes)
                result["image_path"] = img_path

            if harness.evolution_log.entries:
                last = harness.evolution_log.entries[-1]
                result["score"] = last.verifier_score or 0.0
                result["node_count"] = last.node_count_after

            best_score = max(
                (e.verifier_score or 0.0 for e in harness.evolution_log.entries),
                default=0.0,
            )
            result["score"] = best_score

    except Exception as exc:
        result["error"] = str(exc)
        log.error("Prompt %d failed: %s", idx, exc)

    return result


class BenchmarkRunner:
    """Run a benchmark suite through ComfyClaw."""

    def __init__(self, config: BenchmarkConfig) -> None:
        self.config = config
        self.output_dir = os.path.join(config.output_dir, config.name)

    def run(self) -> BenchmarkResult:
        """Execute the full benchmark and return aggregated results."""
        cfg = self.config
        os.makedirs(self.output_dir, exist_ok=True)

        prompts = self._load_prompts()
        if cfg.max_prompts:
            prompts = prompts[: cfg.max_prompts]

        log.info("Running %s benchmark: %d prompts", cfg.suite, len(prompts))

        harness_kwargs = {
            "api_key": cfg.api_key,
            "server_address": cfg.server_address,
            "model": cfg.model,
            "max_iterations": cfg.max_iterations,
            "image_model": cfg.image_model,
            "verifier_model": cfg.verifier_model,
            "_workflow_path": cfg.workflow_path,
        }

        all_results: list[dict] = []

        if cfg.num_workers <= 1:
            for idx, prompt, meta in prompts:
                res = _run_single_prompt(
                    idx, prompt, meta, self.output_dir, harness_kwargs
                )
                all_results.append(res)
                log.info(
                    "Prompt %d/%d: score=%.3f latency=%.1fs",
                    idx + 1, len(prompts), res["score"], res["latency_s"],
                )
        else:
            with ProcessPoolExecutor(max_workers=cfg.num_workers) as pool:
                futures = {
                    pool.submit(
                        _run_single_prompt,
                        idx, prompt, meta, self.output_dir, harness_kwargs,
                    ): idx
                    for idx, prompt, meta in prompts
                }
                for future in as_completed(futures):
                    res = future.result()
                    all_results.append(res)
                    log.info(
                        "Prompt %d: score=%.3f",
                        res["index"], res["score"],
                    )

        all_results.sort(key=lambda r: r["index"])
        return self._aggregate(prompts, all_results)

    def _load_prompts(self) -> list[tuple[int, str, dict]]:
        """Load prompts using the appropriate adapter."""
        cfg = self.config
        if cfg.suite == "geneval2":
            from .geneval2 import load_geneval2

            return load_geneval2(cfg.data_path)
        elif cfg.suite == "crea":
            from .crea import load_crea

            return load_crea(cfg.data_path)
        elif cfg.suite == "oneig":
            from .oneig import load_oneig

            return load_oneig(cfg.data_path)
        else:
            raise ValueError(f"Unknown benchmark suite: {cfg.suite}")

    def _aggregate(
        self,
        prompts: list[tuple[int, str, dict]],
        results: list[dict],
    ) -> BenchmarkResult:
        """Compute aggregate metrics and save to disk."""
        completed = [r for r in results if r["error"] is None and r["image_path"]]
        failed = [r for r in results if r["error"] is not None]

        scores = [r["score"] for r in completed]
        latencies = [r["latency_s"] for r in completed]

        mean_score = sum(scores) / len(scores) if scores else 0.0
        mean_latency = sum(latencies) / len(latencies) if latencies else 0.0

        # Save per-prompt results
        mapping = {r["prompt"]: r["image_path"] for r in completed if r["image_path"]}
        mapping_path = os.path.join(self.output_dir, "image_paths.json")
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)

        # Save detailed results
        details_path = os.path.join(self.output_dir, "results.json")
        with open(details_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        result = BenchmarkResult(
            suite=self.config.suite,
            name=self.config.name,
            total_prompts=len(prompts),
            completed=len(completed),
            failed=len(failed),
            mean_score=mean_score,
            scores=scores,
            mean_latency_s=mean_latency,
            per_prompt=results,
        )

        # Save summary
        summary_path = os.path.join(self.output_dir, "summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "suite": result.suite,
                    "name": result.name,
                    "total_prompts": result.total_prompts,
                    "completed": result.completed,
                    "failed": result.failed,
                    "mean_score": result.mean_score,
                    "mean_latency_s": result.mean_latency_s,
                    "metrics": result.metrics,
                },
                f, indent=2,
            )

        log.info(result.summary())
        return result
