import json

# Load results
with open('results_batch_20260614_221801.json') as f:
    results = json.load(f)

# Get one GOOD response from each algorithm
sample_good = {}
for exp in results:
    algo = exp['algorithm']
    if algo not in sample_good and exp.get('response') and len(exp.get('response', '')) > 1000:
        sample_good[algo] = {
            'instance': exp['instance_title'],
            'persona': exp['persona'],
            'response': exp['response'][:500] + '...' if len(exp.get('response', '')) > 500 else exp['response']
        }

# Print samples
for algo, data in sample_good.items():
    print(f"\n{'='*60}")
    print(f"ALGORITHM: {algo.upper()}")
    print(f"Instance: {data['instance']}")
    print(f"Persona: {data['persona']}")
    print(f"{'='*60}")
    print(data['response'])
    print()