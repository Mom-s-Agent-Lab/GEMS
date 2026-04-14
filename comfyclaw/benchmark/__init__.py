"""
ComfyClaw benchmark integration for T2I evaluation.

Adapters for GenEval2, CREA, and OneIG-EN benchmarks that drive ComfyClaw's
full pipeline (explore -> build -> generate -> verify -> evolve) on
standardised prompt sets and collect quantitative metrics.
"""

from .runner import BenchmarkRunner, BenchmarkConfig, BenchmarkResult

__all__ = ["BenchmarkRunner", "BenchmarkConfig", "BenchmarkResult"]
