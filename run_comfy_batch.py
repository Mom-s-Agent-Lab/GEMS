"""Parallel batch runner for the GEMS ComfyUI line.

Fans a list of prompts out across one or more ComfyUI servers and/or
multiple client workers per server.  Each worker owns its own
:class:`agent.comfy_gems.ComfyGEMS` instance, so the full
decompose → generate → verify → refine pipeline runs independently per
prompt.

Why parallelism helps here, even though a single ComfyUI server
serialises its job queue:

* the MLLM round-trips (decompose / verify / refine) dominate wall time
  for short-prompt workloads, and they overlap cleanly with ComfyUI
  work when ``--workers-per-server`` > 1;
* if you have N ComfyUI servers reachable (e.g. different GPUs or
  machines), pass them all in ``--comfyui-servers`` and the runner will
  shard prompts across them round-robin.

Typical usage
-------------

.. code-block:: bash

    # 1 ComfyUI server, 2 client workers overlapping MLLM + ComfyUI:
    python run_comfy_batch.py \\
        --prompts prompts.jsonl \\
        --output-dir results/my_run \\
        --model z-image-turbo \\
        --comfyui-servers 127.0.0.1:8188 \\
        --workers-per-server 2 \\
        --max-iterations 5

    # 4 ComfyUI servers (one worker each, auto):
    python run_comfy_batch.py \\
        --prompts prompts.jsonl \\
        --output-dir results/my_run \\
        --model qwen-image-2512 \\
        --comfyui-servers host1:8188,host2:8188,host3:8188,host4:8188

Input format
------------

``--prompts`` accepts either

* a ``.jsonl`` file with one JSON object per line (``{"prompt": "..."}``
  plus any extra fields, which are passed through to the agent), or
* a plain ``.txt`` file with one prompt per non-empty line.

Output layout
-------------

::

    <output-dir>/
      index.json                       # {prompt: rel_path} for resume
      images/
        prompt_00000.png               # best image of each prompt
        prompt_00001.png
        ...
      traces/
        prompt_00000/
          trace.json
          best.png
          round_1.png, round_2.png, ...
          workflows/workflow_001.json  # every submitted workflow
        ...
      logs/
        worker_0.log
        worker_1.log
        ...

Resume
------

Re-running the same command skips any prompt whose entry already lives
in ``index.json`` — useful after a crash or OOM.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
import time
import traceback
from pathlib import Path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Parallel batch runner for ComfyGEMS.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--prompts",
        required=True,
        help="Path to .jsonl or .txt file containing prompts.",
    )
    p.add_argument(
        "--output-dir",
        required=True,
        help="Where to write images/traces/index.",
    )
    p.add_argument(
        "--model",
        default="qwen-image-2512",
        help="ComfyGEMS model (qwen-image-2512 / z-image-turbo / "
             "flux-klein-9b / longcat-image, aliases accepted).",
    )
    p.add_argument(
        "--comfyui-servers",
        default=os.environ.get("COMFYUI_SERVER", "127.0.0.1:8188"),
        help="Comma-separated list of ComfyUI host:port endpoints. "
             "Prompts are sharded round-robin across them.",
    )
    p.add_argument(
        "--workers-per-server",
        type=int,
        default=1,
        help="Number of client workers to spawn PER ComfyUI server. "
             "Increase to overlap MLLM HTTP latency with ComfyUI work.",
    )
    p.add_argument(
        "--max-iterations",
        type=int,
        default=int(os.environ.get("GEMS_MAX_ITERATIONS", "5")),
        help="Max decompose/verify/refine rounds per prompt.",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Fix KSampler / RandomNoise seed (reproducibility).",
    )
    p.add_argument(
        "--workflow-timeout",
        type=int,
        default=600,
        help="Seconds to wait for each ComfyUI job.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N prompts (after dedup).",
    )
    p.add_argument(
        "--save-all-rounds",
        action="store_true",
        help="Also dump every intermediate round image under traces/.",
    )
    p.add_argument(
        "--save-workflows",
        action="store_true",
        default=True,
        help="Dump every submitted workflow JSON under traces/",
    )
    p.add_argument(
        "--no-save-workflows",
        dest="save_workflows",
        action="store_false",
    )
    p.add_argument(
        "--start-method",
        choices=("spawn", "forkserver", "fork"),
        default="spawn",
        help="Multiprocessing start method. 'spawn' is safest; 'fork' "
             "is faster but unsafe with many HTTP clients / CUDA.",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

def _load_prompts(path: str) -> list[dict]:
    ext = os.path.splitext(path)[1].lower()
    items: list[dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        if ext == ".jsonl":
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if "prompt" not in obj:
                    raise ValueError(
                        f"Every JSONL entry must contain a 'prompt' field "
                        f"(got keys: {list(obj.keys())})."
                    )
                items.append(obj)
        else:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                items.append({"prompt": line})
    return items


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

def _worker(
    rank: int,
    server: str,
    job_queue: "mp.Queue",
    result_queue: "mp.Queue",
    args_dict: dict,
) -> None:
    # Everything heavy is imported inside the child (spawn-safe,
    # friendlier to torch / CUDA init if any downstream hook uses it).
    from agent.comfy_gems import ComfyGEMS

    output_dir = Path(args_dict["output_dir"])
    log_path = output_dir / "logs" / f"worker_{rank}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(log_path, "a", buffering=1, encoding="utf-8")
    # Redirect stdout/stderr so the many print()s inside GEMS don't
    # interleave across workers.
    sys.stdout = log_fh
    sys.stderr = log_fh

    def _log(msg: str) -> None:
        print(f"[worker {rank} @ {server}] {msg}", flush=True)

    _log(f"spawning ComfyGEMS(model={args_dict['model']!r})")
    try:
        agent = ComfyGEMS(
            model=args_dict["model"],
            comfyui_server=server,
            max_iterations=args_dict["max_iterations"],
            seed=args_dict["seed"],
            workflow_timeout=args_dict["workflow_timeout"],
            workflow_log_dir=None,  # set per-prompt below
        )
    except Exception as exc:
        _log(f"failed to init agent: {exc}\n{traceback.format_exc()}")
        result_queue.put({"rank": rank, "fatal": str(exc)})
        return

    while True:
        job = job_queue.get()
        if job is None:
            _log("received sentinel, exiting")
            break

        idx: int = job["idx"]
        item: dict = job["item"]
        prompt: str = item["prompt"]
        trace_dir = output_dir / "traces" / f"prompt_{idx:05d}"
        trace_dir.mkdir(parents=True, exist_ok=True)
        img_dir = output_dir / "images"
        img_dir.mkdir(parents=True, exist_ok=True)

        if args_dict["save_workflows"]:
            agent.workflow_log_dir = str(trace_dir / "workflows")
            os.makedirs(agent.workflow_log_dir, exist_ok=True)
        else:
            agent.workflow_log_dir = None
        agent._workflow_counter = 0  # fresh numbering per prompt

        t0 = time.time()
        _log(f"[{idx:05d}] prompt={prompt!r}")
        try:
            result = agent.run_with_trace(item)
        except Exception as exc:
            _log(f"[{idx:05d}] FAILED: {exc}\n{traceback.format_exc()}")
            result_queue.put({
                "rank": rank,
                "idx": idx,
                "prompt": prompt,
                "error": str(exc),
                "elapsed": time.time() - t0,
            })
            continue

        elapsed = time.time() - t0

        img_rel = f"images/prompt_{idx:05d}.png"
        img_abs = output_dir / img_rel
        with open(img_abs, "wb") as f:
            f.write(result["best_image"])
        with open(trace_dir / "best.png", "wb") as f:
            f.write(result["best_image"])
        with open(trace_dir / "trace.json", "w", encoding="utf-8") as f:
            json.dump(result["trace"], f, indent=2, ensure_ascii=False)
        if args_dict["save_all_rounds"]:
            for i, img_bytes in enumerate(result["all_images"], start=1):
                with open(trace_dir / f"round_{i}.png", "wb") as f:
                    f.write(img_bytes)

        _log(
            f"[{idx:05d}] done in {elapsed:.1f}s "
            f"rounds={result['trace']['total_rounds']} "
            f"success={result['trace']['success']}"
        )
        result_queue.put({
            "rank": rank,
            "idx": idx,
            "prompt": prompt,
            "img_path": img_rel,
            "rounds": result["trace"]["total_rounds"],
            "success": bool(result["trace"]["success"]),
            "elapsed": elapsed,
        })

    log_fh.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = _parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "images").mkdir(exist_ok=True)
    (output_dir / "traces").mkdir(exist_ok=True)
    (output_dir / "logs").mkdir(exist_ok=True)

    all_items = _load_prompts(args.prompts)
    all_items = [(i, item) for i, item in enumerate(all_items)]
    if args.limit is not None:
        all_items = all_items[: args.limit]
    print(f"Loaded {len(all_items)} prompts from {args.prompts}")

    index_path = output_dir / "index.json"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
        print(f"Resuming: {len(index)} prompts already done.")
    else:
        index = {}

    todo = [(i, it) for i, it in all_items if it["prompt"] not in index]
    if not todo:
        print("Nothing to do — everything is already in index.json.")
        return
    print(f"To process this run: {len(todo)}")

    servers = [s.strip() for s in args.comfyui_servers.split(",") if s.strip()]
    if not servers:
        raise SystemExit("--comfyui-servers is empty")
    workers_per_server = max(1, args.workers_per_server)
    total_workers = len(servers) * workers_per_server
    print(
        f"Servers: {servers} · workers/server: {workers_per_server} · "
        f"total workers: {total_workers}"
    )

    ctx = mp.get_context(args.start_method)
    job_queue: "mp.Queue" = ctx.Queue()
    result_queue: "mp.Queue" = ctx.Queue()

    for idx, item in todo:
        job_queue.put({"idx": idx, "item": item})
    for _ in range(total_workers):
        job_queue.put(None)  # sentinel per worker

    args_dict = dict(
        output_dir=str(output_dir),
        model=args.model,
        max_iterations=args.max_iterations,
        seed=args.seed,
        workflow_timeout=args.workflow_timeout,
        save_all_rounds=args.save_all_rounds,
        save_workflows=args.save_workflows,
    )

    procs = []
    worker_rank = 0
    for server in servers:
        for _ in range(workers_per_server):
            p = ctx.Process(
                target=_worker,
                args=(worker_rank, server, job_queue, result_queue, args_dict),
                daemon=False,
            )
            p.start()
            procs.append(p)
            worker_rank += 1

    t_start = time.time()
    done = 0
    failed = 0
    try:
        while done + failed < len(todo):
            msg = result_queue.get()
            if "fatal" in msg:
                print(
                    f"[FATAL] worker {msg['rank']} died: {msg['fatal']} — "
                    f"its remaining jobs will block. Aborting."
                )
                break
            if "error" in msg:
                failed += 1
                print(
                    f"  ✗ [{msg['idx']:05d}] {msg['error']} "
                    f"({msg['elapsed']:.1f}s)  [{done+failed}/{len(todo)}]"
                )
                continue
            done += 1
            index[msg["prompt"]] = msg["img_path"]
            # flush index every success so we can resume cleanly
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2, ensure_ascii=False)
            print(
                f"  ✓ [{msg['idx']:05d}] rounds={msg['rounds']} "
                f"success={msg['success']} ({msg['elapsed']:.1f}s)  "
                f"[{done+failed}/{len(todo)}]"
            )
    finally:
        for p in procs:
            p.join(timeout=10)
            if p.is_alive():
                p.terminate()

    wall = time.time() - t_start
    print(
        f"\n[done] {done} ok, {failed} failed in {wall:.1f}s "
        f"({wall / max(done, 1):.1f}s/prompt avg) "
        f"→ {output_dir}"
    )


if __name__ == "__main__":
    main()
