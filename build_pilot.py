"""Build a fixed source-document-assisted pilot with identical context per model."""
import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
rows = list(csv.DictReader((ROOT / 'data/officeqa_pro.csv').open()))[:10]
tests = []
for row in rows:
    terms = Counter(re.findall(r'[a-z0-9]+', row['question'].lower()))
    chunks = []
    names = sorted(set(re.findall(r'treasury_bulletin_\d{4}_\d{2}\.txt', row['source_files'])))
    for name in names:
        text = (ROOT / 'data/corpus/treasury_bulletins_parsed/transformed' / name).read_text()
        for start in range(0, len(text), 1800):
            chunk = text[start:start + 2400]
            words = Counter(re.findall(r'[a-z0-9]+', chunk.lower()))
            score = sum(min(words[word], 3) * count for word, count in terms.items() if len(word) > 2)
            chunks.append((score, name, start, chunk))
    selected = sorted(chunks, key=lambda item: (-item[0], item[1], item[2]))[:12]
    context = '\n\n'.join(f'[{name}, character {start}]\n{chunk}' for _, name, start, chunk in selected)
    tests.append({
        'description': row['uid'],
        'vars': {'question': row['question'], 'context': context},
        'metadata': {'uid': row['uid'], 'referenceAnswer': row['answer'], 'sourceFiles': names},
        'assert': [{'type': 'python', 'value': 'file://score.py', 'metric': 'accuracy'}],
    })
(ROOT / 'data/pilot-tests.json').write_text(json.dumps(tests, indent=2))
config = {
    'description': 'OfficeQA Pro first 10 questions; reference-document lexical retrieval; 1% tolerance',
    'prompts': ['Answer the financial question using the supplied document excerpts. Compute carefully. Return only the final answer, with its units. If the excerpts are insufficient, say insufficient evidence.\n\nQuestion: {{question}}\n\nExcerpts:\n{{context}}'],
    'providers': [
        {'id': 'file://budget-provider.mjs', 'label': model, 'config': {'model': model, 'vendor': vendor, 'inputRate': inp, 'outputRate': out}}
        for model, vendor, inp, out in [
            ('gpt-5.5', 'openai', 5, 30), ('gpt-5.6-sol', 'openai', 4, 20),
            ('claude-opus-4-8', 'anthropic', 5, 25), ('claude-fable-5', 'anthropic', 10, 50),
        ]
    ],
    'tests': 'file://data/pilot-tests.json',
    'evaluateOptions': {'maxConcurrency': 1, 'cache': False},
}
(ROOT / 'pilot.json').write_text(json.dumps(config, indent=2))
print('Prepared 10 questions with at most 12 excerpts each; answer keys stay in grader metadata.')
