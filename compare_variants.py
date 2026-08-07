#!/usr/bin/env python3
"""
compare_variants.py
===================
Analyze responses from 3 Dijkstra variants to measure "drift".

Drift = deviation from describing the actual algorithm procedure.
Looks for:
  - Off-topic tangents (cost calculations, infrastructure details)
  - Anachronistic knowledge (modern tech, modern methods)
  - Vagueness (doesn't describe steps clearly)
  - Length and coherence
"""

import json
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(__file__))

try:
    from experiment_db import get_experiments
except ImportError:
    print("ERROR: Could not import experiment_db")
    sys.exit(1)


def analyze_drift(response_text: str) -> dict:
    """
    Heuristic analysis of response quality/drift.
    Returns a dict with drift indicators.
    """
    if not response_text:
        return {
            "length": 0,
            "has_content": False,
            "drift_indicators": ["No response"],
            "score": 0
        }
    
    text = response_text.lower()
    length = len(response_text)
    
    # Drift indicators (bad things that suggest off-topic)
    drift_keywords = [
        "cost", "expense", "pound sterling", "expensive",  # Cost focus
        "build", "construction", "labour", "workers",      # Infrastructure focus
        "modern", "computer", "algorithm", "graph theory", "dijkstra",  # Anachronism
        "unfortunately", "however", "but this",            # Hedging
        "cannot", "impossible", "unable",                  # Negativity
    ]
    
    drift_found = []
    for kw in drift_keywords:
        if kw in text:
            drift_found.append(kw)
    
    # Good indicators (signs of staying on-topic)
    good_keywords = [
        "procedure", "steps", "process", "method",
        "decide", "choose", "select", "determine",
        "first", "then", "next", "finally",
    ]
    
    good_count = sum(1 for kw in good_keywords if kw in text)
    
    # Simple heuristic score: 0-100
    # Penalize drift, reward structure
    score = 50  # baseline
    score += min(good_count * 5, 30)  # up to 30 points for structure
    score -= len(drift_found) * 8  # -8 per drift keyword, up to -80
    score = max(0, min(100, score))
    
    return {
        "length": length,
        "has_content": True,
        "good_keywords": good_count,
        "drift_indicators": drift_found,
        "drift_score": len(drift_found),
        "quality_score": score,
    }


def compare_variants():
    """Main comparison."""
    experiments = get_experiments(algorithm="dijkstra")
    
    if not experiments:
        print("ERROR: No Dijkstra experiments found in DB")
        sys.exit(1)
    
    # Filter to seed 0 only
    experiments = [e for e in experiments if e.get("seed") == 0]
    
    # Organize by variant and persona
    by_variant = defaultdict(lambda: {})
    for exp in experiments:
        variant = exp["instance_id"]
        persona = exp["persona"]
        by_variant[variant][persona] = exp
    
    # Sort variants in order: original, v2, v3
    variant_order = ["dijkstra_1", "dijkstra_1_v2", "dijkstra_1_v3"]
    variants_present = [v for v in variant_order if v in by_variant]
    
    if not variants_present:
        print("ERROR: No dijkstra variants found")
        sys.exit(1)
    
    print("\n" + "="*90)
    print("DIJKSTRA VARIANT COMPARISON — SEED 0 ONLY")
    print("="*90)
    print()
    
    # Header
    print(f"{'Variant':<25} {'Persona':<12} {'Status':<12} {'Length':<10} {'Quality':<10}")
    print("-" * 90)
    
    variant_stats = defaultdict(lambda: {"scores": [], "total": 0})
    
    for variant in variants_present:
        personas_data = by_variant[variant]
        
        for persona in ["scholar", "mechanist"]:
            if persona not in personas_data:
                print(f"{variant:<25} {persona:<12} {'MISSING':<12}")
                continue
            
            exp = personas_data[persona]
            response = exp.get("response")
            status = exp.get("status", "unknown")
            
            if status == "completed" and response:
                analysis = analyze_drift(response)
                quality = analysis["quality_score"]
                length = analysis["length"]
                drift_indicators = analysis["drift_indicators"]
                
                variant_stats[variant]["scores"].append(quality)
                variant_stats[variant]["total"] += 1
                
                indicator_str = f" [drift: {', '.join(drift_indicators[:3])}]" if drift_indicators else ""
                
                print(f"{variant:<25} {persona:<12} {status:<12} {length:<10} {quality:<10.0f}{indicator_str}")
            else:
                print(f"{variant:<25} {persona:<12} {status:<12}")
    
    print("\n" + "="*90)
    print("VARIANT AVERAGES")
    print("="*90)
    
    averages = {}
    for variant in variants_present:
        if variant_stats[variant]["total"] > 0:
            avg = sum(variant_stats[variant]["scores"]) / variant_stats[variant]["total"]
            averages[variant] = avg
            print(f"{variant:<25} Avg quality: {avg:.1f}/100")
    
    if averages:
        best_variant = max(averages, key=averages.get)
        print(f"\n✓ BEST VARIANT: {best_variant} (avg {averages[best_variant]:.1f})")
        print(f"  → Use this prompt framing for full batch run")
    
    print("\n" + "="*90)


if __name__ == "__main__":
    compare_variants()
