"""
run_experiments.py
==================
Batch experiment runner for the Anachronistic LLM research project.

Loads all disguised CS problems from micro_problems.json, runs each
through GPT-1900-instruct via Modal, and logs every prompt + response
to SQLite via experiment_db.py.

Usage:
    # Full batch — all algorithms, both personas, 5 seeds each
    python run_experiments.py

    # Single algorithm test
    python run_experiments.py --algorithm dijkstra

    # Single persona only
    python run_experiments.py --persona scholar

    # Dry run — prints what would be run without calling Modal
    python run_experiments.py --dry-run

    # Resume — skips already-completed experiments
    python run_experiments.py --resume
"""

import argparse
import json
import time
import uuid
import os
from datetime import datetime
from typing import Optional

import modal

# ─── Load problem definitions ───
PROBLEMS_PATH = os.path.join(os.path.dirname(__file__), "micro_problems.json")
with open(PROBLEMS_PATH) as f:
    PROBLEMS = json.load(f)

# ─── Import experiment DB ───
from experiment_db import (
    create_batch_run,
    create_experiment,
    complete_experiment,
    fail_experiment,
    update_batch_progress,
    complete_batch_run,
    get_experiments,
    get_summary_stats,
    export_all_results,
)

# ─── Modal function lookup ───
# Requires: modal deploy modal_test.py has been run first
def get_modal_fn():
    try:
        return modal.Function.from_name("gpt1900-test", "run_prompt")
    except Exception as e:
        raise RuntimeError(
            f"Could not find Modal function 'run_prompt' in app 'gpt1900-test'.\n"
            f"Make sure you have run: modal deploy modal_test.py\n"
            f"Original error: {e}"
        )


def build_full_prompt(system_prompt: str, user_prompt: str) -> str:
    """
    Combine persona system prompt with the disguised problem.
    GPT-1900-instruct uses a simple Q/A format.
    """
    return f"{system_prompt}\n\nQuestion: {user_prompt}\n\nAnswer:"


def run_single_experiment(
    run_prompt_fn,
    algorithm: str,
    instance: dict,
    persona_name: str,
    persona_prompt: str,
    seed: int,
    dry_run: bool = False,
    temperature: float = 0.65,
) -> dict:
    """
    Run a single experiment and return a result dict.
    """
    exp_id = str(uuid.uuid4())[:12]
    full_id = f"{algorithm}_{instance['id']}_{persona_name}_seed{seed}_{exp_id}"

    system_prompt = persona_prompt
    user_prompt = instance["prompt"]
    full_prompt = build_full_prompt(system_prompt, user_prompt)

    # Log experiment to DB before running
    create_experiment(
        exp_id=full_id,
        algorithm=algorithm,
        instance_id=instance["id"],
        instance_title=instance["title"],
        domain=instance["domain"],
        persona=persona_name,
        model="gpt1900-instruct-v3-sft",
        seed=seed,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )

    if dry_run:
        print(f"  [DRY RUN] Would run: {full_id}")
        print(f"  Prompt preview: {full_prompt[:120]}...")
        return {"id": full_id, "status": "dry_run"}

    print(f"  Running: {algorithm} | {instance['title']} | {persona_name} | seed={seed}")

    start = time.time()
    try:
        response = run_prompt_fn.remote(full_prompt)
        duration = time.time() - start

        # Strip the prompt echo if the model repeats it
        if response and full_prompt[:50] in response:
            response = response.replace(full_prompt, "").strip()

        complete_experiment(full_id, response or "", duration)

        print(f"  ✓ Done in {duration:.1f}s | Response: {len(response or '')} chars")
        return {
            "id": full_id,
            "status": "completed",
            "response": response,
            "duration": duration,
        }

    except Exception as e:
        duration = time.time() - start
        error_msg = str(e)
        fail_experiment(full_id, error_msg)
        print(f"  ✗ Failed after {duration:.1f}s: {error_msg[:80]}")
        return {"id": full_id, "status": "failed", "error": error_msg}


def run_batch(
    algorithms: Optional[list] = None,
    personas: Optional[list] = None,
    seeds: Optional[list] = None,
    dry_run: bool = False,
    resume: bool = False,
    temperature: float = 0.65,
):
    """
    Main batch runner. Iterates over all combinations of:
    algorithm × instance × persona × seed
    """
    # Defaults
    all_algorithms = list(PROBLEMS["algorithms"].keys())
    all_personas = list(PROBLEMS["personas"].keys())
    default_seeds = [0, 1, 2, 3, 4]

    target_algorithms = algorithms or all_algorithms
    target_personas = personas or all_personas
    target_seeds = seeds or default_seeds

    # Validate
    for alg in target_algorithms:
        if alg not in PROBLEMS["algorithms"]:
            raise ValueError(f"Unknown algorithm: {alg}. "
                           f"Valid: {all_algorithms}")
    for p in target_personas:
        if p not in PROBLEMS["personas"]:
            raise ValueError(f"Unknown persona: {p}. "
                           f"Valid: {all_personas}")

    # Count total experiments
    total = sum(
        len(PROBLEMS["algorithms"][alg]["instances"])
        for alg in target_algorithms
    ) * len(target_personas) * len(target_seeds)

    print("\n" + "="*60)
    print("ANACHRONISTIC LLM — BATCH EXPERIMENT RUNNER")
    print("="*60)
    print(f"Algorithms : {target_algorithms}")
    print(f"Personas   : {target_personas}")
    print(f"Seeds      : {target_seeds}")
    print(f"Total runs : {total}")
    print(f"Dry run    : {dry_run}")
    print(f"Resume     : {resume}")
    print("="*60 + "\n")

    if not dry_run:
        run_prompt_fn = get_modal_fn()
    else:
        run_prompt_fn = None

    # Create batch record
    batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    create_batch_run(
        batch_id=batch_id,
        description=f"Batch run: {target_algorithms} | {target_personas} | seeds {target_seeds}",
        algorithms=target_algorithms,
        personas=target_personas,
        seeds=target_seeds,
        total=total,
    )

    # Get already-completed experiment IDs if resuming
    completed_ids = set()
    if resume:
        existing = get_experiments(status="completed")
        for exp in existing:
            # Match on algorithm + instance + persona + seed
            key = f"{exp['algorithm']}_{exp['instance_id']}_{exp['persona']}_seed"
            # Extract seed from experiment id
            parts = exp["id"].split("_seed")
            if len(parts) > 1:
                seed_part = parts[1].split("_")[0]
                completed_ids.add(f"{exp['algorithm']}_{exp['instance_id']}_{exp['persona']}_{seed_part}")
        print(f"Resuming: {len(completed_ids)} experiments already completed, skipping.\n")

    completed = 0
    failed = 0
    results = []

    # Main experiment loop
    for algorithm in target_algorithms:
        algo_data = PROBLEMS["algorithms"][algorithm]
        instances = algo_data["instances"]

        print(f"\n{'─'*60}")
        print(f"ALGORITHM: {algo_data['target_algorithm']} "
              f"| Complexity: {algo_data['optimal_complexity']} "
              f"| Corpus: {algo_data['corpus_status']}")
        print(f"{'─'*60}")

        for instance in instances:
            print(f"\n  Instance: {instance['title']} ({instance['domain']})")

            for persona_name in target_personas:
                persona_prompt = PROBLEMS["personas"][persona_name]

                for seed in target_seeds:
                    # Check if already done (resume mode)
                    resume_key = f"{algorithm}_{instance['id']}_{persona_name}_{seed}"
                    if resume and resume_key in completed_ids:
                        print(f"  [SKIP] Already completed: {resume_key}")
                        completed += 1
                        continue

                    result = run_single_experiment(
                        run_prompt_fn=run_prompt_fn,
                        algorithm=algorithm,
                        instance=instance,
                        persona_name=persona_name,
                        persona_prompt=persona_prompt,
                        seed=seed,
                        dry_run=dry_run,
                        temperature=temperature,
                    )

                    results.append(result)
                    if result["status"] == "completed":
                        completed += 1
                    elif result["status"] == "failed":
                        failed += 1

                    # Update batch progress every 5 runs
                    if (completed + failed) % 5 == 0:
                        update_batch_progress(batch_id, completed, failed)

                    # Small delay between calls to avoid rate limits
                    if not dry_run:
                        time.sleep(1)

    # Finalize
    update_batch_progress(batch_id, completed, failed)
    complete_batch_run(batch_id)

    print(f"\n{'='*60}")
    print(f"BATCH COMPLETE: {batch_id}")
    print(f"  Completed : {completed}/{total}")
    print(f"  Failed    : {failed}/{total}")
    print(f"{'='*60}\n")

    # Export results
    if not dry_run and completed > 0:
        output_path = f"results_{batch_id}.json"
        export_all_results(output_path)
        print(f"Results exported to: {output_path}")

    return {
        "batch_id": batch_id,
        "completed": completed,
        "failed": failed,
        "total": total,
    }


def print_stats():
    """Print current database statistics."""
    stats = get_summary_stats()
    print("\n" + "="*60)
    print("EXPERIMENT DATABASE STATISTICS")
    print("="*60)

    overall = stats.get("overall", {})
    print(f"\nOverall:")
    print(f"  Total experiments : {overall.get('total', 0)}")
    print(f"  Completed         : {overall.get('completed', 0)}")
    print(f"  Failed            : {overall.get('failed', 0)}")
    print(f"  Avg duration      : {overall.get('avg_duration', 0):.1f}s")
    print(f"  Avg response len  : {overall.get('avg_length', 0):.0f} chars")

    print(f"\nBy Algorithm:")
    for row in stats.get("by_algorithm", []):
        print(f"  {row['algorithm']:20s} | {row['completed']}/{row['total']} done "
              f"| avg {row['avg_length']:.0f} chars")

    print(f"\nBy Persona:")
    for row in stats.get("by_persona", []):
        print(f"  {row['persona']:15s} | {row['total']} experiments "
              f"| avg {row['avg_length']:.0f} chars")
    print()


# ─── CLI ───

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run batch experiments for Anachronistic LLM research"
    )
    parser.add_argument(
        "--algorithm", "-a",
        nargs="+",
        choices=list(PROBLEMS["algorithms"].keys()),
        help="Algorithms to run (default: all)"
    )
    parser.add_argument(
        "--persona", "-p",
        nargs="+",
        choices=["scholar", "mechanist"],
        help="Personas to use (default: both)"
    )
    parser.add_argument(
        "--seeds", "-s",
        nargs="+",
        type=int,
        default=[0, 1, 2, 3, 4],
        help="Random seeds for multiple runs (default: 0 1 2 3 4)"
    )
    parser.add_argument(
        "--temperature", "-t",
        type=float,
        default=0.65,
        help="Sampling temperature (default: 0.65)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be run without calling Modal"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip already-completed experiments"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print database statistics and exit"
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export all results to JSON and exit"
    )

    args = parser.parse_args()

    if args.stats:
        print_stats()
    elif args.export:
        path = export_all_results()
        print(f"Exported to: {path}")
    else:
        run_batch(
            algorithms=args.algorithm,
            personas=args.persona,
            seeds=args.seeds,
            dry_run=args.dry_run,
            resume=args.resume,
            temperature=args.temperature,
        )
