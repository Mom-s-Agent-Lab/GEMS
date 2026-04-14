"""
CLI entry point for ComfyClaw benchmarks.

Usage::

    python -m comfyclaw.benchmark.cli \\
        --suite geneval2 \\
        --name baseline-v1 \\
        --data-path path/to/geneval2_data.jsonl \\
        --max-iterations 3 \\
        --max-prompts 10
"""

from __future__ import annotations

import argparse
import logging
import sys

from .runner import BenchmarkConfig, BenchmarkRunner


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="comfyclaw-benchmark",
        description="Run ComfyClaw on T2I evaluation benchmarks",
    )
    parser.add_argument(
        "--suite",
        required=True,
        choices=["geneval2", "crea", "oneig"],
        help="Benchmark suite to run",
    )
    parser.add_argument("--name", required=True, help="Experiment name (output subfolder)")
    parser.add_argument("--data-path", required=True, help="Path to benchmark data file (JSONL)")
    parser.add_argument("--output-dir", default="benchmark_results", help="Output directory")
    parser.add_argument("--max-iterations", type=int, default=3, help="Max iterations per prompt")
    parser.add_argument("--num-workers", type=int, default=1, help="Parallel workers")
    parser.add_argument("--server", default="127.0.0.1:8188", help="ComfyUI server address")
    parser.add_argument("--api-key", default="", help="LLM API key")
    parser.add_argument("--model", default="anthropic/claude-sonnet-4-5", help="LLM model")
    parser.add_argument("--image-model", default=None, help="Pin ComfyUI image model")
    parser.add_argument("--workflow", default=None, help="Base workflow JSON path")
    parser.add_argument("--stage-gated", action="store_true", help="Enable stage-gated tools")
    parser.add_argument("--verifier-model", default=None, help="VLM model for verification")
    parser.add_argument("--max-prompts", type=int, default=None, help="Limit prompts (for testing)")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    config = BenchmarkConfig(
        suite=args.suite,
        name=args.name,
        data_path=args.data_path,
        output_dir=args.output_dir,
        max_iterations=args.max_iterations,
        num_workers=args.num_workers,
        server_address=args.server,
        api_key=args.api_key,
        model=args.model,
        image_model=args.image_model,
        workflow_path=args.workflow,
        stage_gated=args.stage_gated,
        verifier_model=args.verifier_model,
        max_prompts=args.max_prompts,
    )

    runner = BenchmarkRunner(config)
    result = runner.run()

    print("\n" + "=" * 50)
    print(result.summary())
    print("=" * 50)

    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
