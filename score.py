"""Promptfoo Python assertion using the benchmark's official numerical scorer."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "upstream"))
from reward import score_answer


def get_assert(output, context):
    reference = context["test"]["metadata"]["referenceAnswer"]
    score = score_answer(reference, str(output), tolerance=0.01)
    return {
        "pass": score == 1.0,
        "score": score,
        "reason": "Official OfficeQA scorer with 1% relative tolerance",
    }
