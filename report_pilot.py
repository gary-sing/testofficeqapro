"""Summarize observed runs and plot quality against measured token charges."""
import csv
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / 'results'
MODELS = ['gpt-5.5', 'gpt-5.6-sol', 'claude-opus-4-8', 'claude-fable-5']
ledger = [json.loads(line) for line in (RESULTS / 'pilot-ledger.jsonl').read_text().splitlines()]
tests = json.loads((ROOT / 'data/pilot-tests.json').read_text())
scoring_code = '''import json,sys
sys.path.insert(0, sys.argv[1])
from reward import score_answer
for item in json.load(sys.stdin):
 print(score_answer(item['reference'],item['output'],tolerance=0.01))
'''
selected = {}
for record in ledger:
    if record['type'] == 'result':
        selected[(record['model'], record['uid'])] = record
items = []
detail = []
for model in MODELS:
    for test in tests:
        uid = test['metadata']['uid']
        record = selected.get((model, uid))
        if record:
            items.append({'reference': test['metadata']['referenceAnswer'], 'output': record['output']})
            detail.append({'model': model, 'uid': uid, 'record': record})
runtime = '/Users/g4singh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
scored = subprocess.run([runtime, '-c', scoring_code, str(ROOT / 'upstream')], input=json.dumps(items), capture_output=True, text=True, check=True)
scores = [float(value) for value in scored.stdout.splitlines()]
for item, score in zip(detail, scores):
    item['score'] = score
summary = []
for model in MODELS:
    records = [item for item in detail if item['model'] == model]
    all_costs = sum(row.get('cost', 0) for row in ledger if row['model'] == model)
    correct = sum(item['score'] for item in records)
    count = len(records)
    summary.append({
        'model': model, 'completed': count, 'questions': 10, 'correct': correct,
        'accuracy': correct / count if count else None,
        'total_cost_usd': all_costs,
        'cost_per_question_usd': all_costs / count if count else None,
        'truncated': sum(bool(item['record']['truncated']) for item in records),
        'status': 'Complete' if count == 10 else 'Partial' if count else 'Blocked — OpenAI credits exhausted',
    })
(RESULTS / 'summary.json').write_text(json.dumps(summary, indent=2))
with (RESULTS / 'summary.csv').open('w', newline='') as target:
    writer = csv.DictWriter(target, fieldnames=list(summary[0]))
    writer.writeheader()
    writer.writerows(summary)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
available = [row for row in summary if row['completed'] == 10]
frontier = [a for a in available if not any(
    b['cost_per_question_usd'] <= a['cost_per_question_usd'] and b['accuracy'] >= a['accuracy']
    and (b['cost_per_question_usd'] < a['cost_per_question_usd'] or b['accuracy'] > a['accuracy'])
    for b in available if b is not a)]
fig, ax = plt.subplots(figsize=(9, 5.8))
for row in available:
    ax.scatter(row['cost_per_question_usd'], 100 * row['accuracy'], s=95, color='#513BC0')
    ax.annotate(row['model'], (row['cost_per_question_usd'], 100 * row['accuracy']), xytext=(8, 10), textcoords='offset points', fontsize=10)
if frontier:
    frontier.sort(key=lambda row: row['cost_per_question_usd'])
    ax.plot([row['cost_per_question_usd'] for row in frontier], [100*row['accuracy'] for row in frontier], '--*', markersize=13, color='#28795D', label='Observed Pareto frontier')
    ax.legend(loc='upper right')
ax.set(title='OfficeQA Pro pilot — quality vs. cost', xlabel='Observed model cost per question (USD, including pilot retries)', ylabel='Accuracy at 1% numerical tolerance (%)', ylim=(-5, 110))
ax.grid(alpha=0.2)
ax.margins(x=0.4)
fig.text(0.12, 0.025, 'First 10 dataset questions. Reference-document lexical retrieval.\nGPT-5.5 and GPT-5.6 Sol blocked by API billing; no accuracy assigned.', fontsize=9, color='#555555')
fig.tight_layout(rect=(0, 0.09, 1, 1))
fig.savefig(RESULTS / 'quality-vs-cost.png', dpi=180)
fig.savefig(RESULTS / 'quality-vs-cost.svg')
print(json.dumps(summary, indent=2))
