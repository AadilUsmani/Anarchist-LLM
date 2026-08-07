#!/usr/bin/env python3
"""
test_dijkstra_variants.py
=========================
Lightweight test runner for Dijkstra prompt variants.
Runs only:
  - dijkstra_1 (original)
  - dijkstra_1_v2 (scaffolded)
  - dijkstra_1_v3 (constrained)

Each variant × both personas (scholar, mechanist) × seed 0 only = 6 runs

Prints responses side-by-side for easy comparison of "drift".
"""

import json
import sys
import os
import argparse

# Add parent to path if running from here
sys.path.insert(0, os.path.dirname(__file__))

try:
    from experiment_db import (
        create_experiment,
        complete_experiment,
        fail_experiment,
        get_experiments,
    )
except ImportError as e:
    print(f"ERROR: Could not import experiment_db. Make sure it's in PYTHONPATH or same dir.\n{e}")
    sys.exit(1)

PROBLEMS_PATH = "micro_problems.json"


def load_problems():
    with open(PROBLEMS_PATH) as f:
        return json.load(f)


def run_test(dry_run=True, resume=False):
    """
    Run 3 Dijkstra variants on seed 0 only.
    """
    problems = load_problems()
    
    # Get only the 3 variants
    dijkstra_algo = problems["algorithms"]["dijkstra"]
    instances = dijkstra_algo["instances"]
    
    # Filter to just the 3 variants
    variants = [i for i in instances if i["id"] in 
                ["dijkstra_1", "dijkstra_1_v2", "dijkstra_1_v3"]]
    
    if len(variants) != 3:
        print(f"ERROR: Expected 3 Dijkstra variants, found {len(variants)}")
        print(f"Found: {[i['id'] for i in variants]}")
        sys.exit(1)
    
    personas = problems["personas"]
    seed = 0
    total = len(variants) * len(personas)
    
    print("\n" + "="*70)
    print("DIJKSTRA VARIANT TEST — SEED 0 ONLY")
    print("="*70)
    print(f"Variants: {[v['id'] for v in variants]}")
    print(f"Personas: {list(personas.keys())}")
    print(f"Total runs: {total}")
    print(f"Dry run: {dry_run}")
    print("="*70 + "\n")
    
    # Get completed IDs if resuming
    completed_ids = set()
    if resume:
        existing = get_experiments(status="completed")
        for exp in existing:
            key = f"{exp['algorithm']}_{exp['instance_id']}_{exp['persona']}_seed{exp['seed']}"
            completed_ids.add(key)
        print(f"Resume mode: {len(completed_ids)} already completed, will skip.\n")
    
    results = []
    
    for variant in variants:
        print(f"\n{'─'*70}")
        print(f"VARIANT: {variant['id']}")
        print(f"Title: {variant['title']}")
        print(f"{'─'*70}\n")
        
        for persona_name, persona_prompt in personas.items():
            exp_key = f"dijkstra_{variant['id']}_{persona_name}_seed{seed}"
            
            if resume and exp_key in completed_ids:
                print(f"  [SKIP] {persona_name:12} — already completed")
                continue
            
            prompt = variant["prompt"]
            
            print(f"  {persona_name.upper():12} (seed={seed})")
            print(f"  Prompt: {prompt[:80]}...")
            
            if dry_run:
                print(f"  [DRY RUN]")
                results.append({
                    "variant": variant["id"],
                    "persona": persona_name,
                    "status": "dry_run",
                    "prompt": prompt
                })
            else:
                # In a real run, would call Modal here
                # For now just log to DB as pending
                exp_id = f"dijkstra_{variant['id']}_{persona_name}_seed{seed}"
                try:
                    create_experiment(
                        exp_id=exp_id,
                        algorithm="dijkstra",
                        instance_id=variant["id"],
                        instance_title=variant["title"],
                        domain=variant["domain"],
                        persona=persona_name,
                        model="gpt1900-instruct-v3-sft",
                        seed=seed,
                        system_prompt=persona_prompt,
                        user_prompt=prompt,
                    )
                    print(f"  → Logged to DB")
                    results.append({
                        "variant": variant["id"],
                        "persona": persona_name,
                        "status": "pending",
                    })
                except Exception as e:
                    print(f"  ✗ Error: {e}")
                    results.append({
                        "variant": variant["id"],
                        "persona": persona_name,
                        "status": "error",
                        "error": str(e),
                    })
            print()
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Total: {len(results)}/{total}")
    print(f"Ready for Modal deployment.")
    print("\nNext steps:")
    print("  1. Ensure modal_test.py is deployed: modal deploy modal_test.py")
    print("  2. Run actual experiments: python run_experiments.py --algorithm dijkstra --resume")
    print("  3. Compare responses with: python compare_variants.py")
    print("="*70 + "\n")
    
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Dijkstra prompt variants")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Print what would run (default: yes)")
    parser.add_argument("--execute", action="store_true",
                        help="Actually log experiments to DB (skips dry-run)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip already-completed experiments")
    
    args = parser.parse_args()
    
    run_test(dry_run=not args.execute, resume=args.resume)
