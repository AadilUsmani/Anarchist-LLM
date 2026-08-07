import json

with open('results_batch_20260614_185124.json') as f:
    results = json.load(f)

print(f'Total experiments in file: {len(results)}')

with_response = [e for e in results if e.get('response')]
print(f'With responses: {len(with_response)}')

for exp in with_response:
    print('='*60)
    print('Algorithm:', exp['algorithm'])
    print('Instance:', exp['instance_title'])
    print('Persona:', exp['persona'])
    print('Status:', exp['status'])
    print('Response:')
    print(exp['response'])
    print()