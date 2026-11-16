"""Convert the official CSV to Promptfoo cases without exposing answers to prompts."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
with (ROOT / "data/officeqa_pro.csv").open(newline="", encoding="utf-8-sig") as source:
    rows = list(csv.DictReader(source))

identifiers = [row["uid"] for row in rows]
if len(rows) != 133 or len(set(identifiers)) != len(rows):
    raise ValueError("Expected the 133 unique OfficeQA Pro questions")

tests = []
for row in rows:
    if not row["question"].strip() or not row["answer"].strip():
        raise ValueError("Missing question or reference answer for " + row["uid"])
    tests.append({
        "description": row["uid"],
        "vars": {"question": row["question"]},
        "metadata": {"uid": row["uid"], "referenceAnswer": row["answer"]},
        "assert": [{
            "type": "python",
            "value": "file://score.py",
            "metric": "OfficeQA accuracy",
        }],
    })

destination = ROOT / "data/tests.json"
destination.write_text(json.dumps(tests, indent=2) + "\n", encoding="utf-8")
print(f"Prepared {len(tests)} cases. Reference answers are grader metadata only.")
