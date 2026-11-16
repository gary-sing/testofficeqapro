# OfficeQA Pro pilot

This evaluation uses the first 10 questions in the downloaded OfficeQA Pro CSV, in dataset order. Every model receives the same question and document excerpts. Reference answers stay in grader metadata and are excluded from model requests.

## Method

The pilot uses reference-document lexical retrieval. It searches only the source documents named by each benchmark record, ranks overlapping 2,400-character chunks by question-term overlap, and supplies the top 12. This gives the system document identities from the benchmark. Results measure this particular source-assisted setup and should be labeled separately from published end-to-end agent results.

The official upstream `reward.py` scores answers at 1% numerical tolerance. The pilot has only 10 questions, so one correct answer changes accuracy by 10 percentage points.

GPT models use medium reasoning effort. Claude models use adaptive thinking with the API's default effort. Generation is capped at 8,192 output/thinking tokens. Initial diagnostic calls used a 4,096-token cap. Truncated diagnostic outputs can be retried and all reported token charges remain included in the cost ledger.

## Budget and records

The custom Promptfoo provider makes sequential calls and reserves a conservative maximum cost before each request. Input reservations use UTF-8 bytes plus overhead as an upper bound on input tokens, with the full output allowance. Reservations are retained for failed or timed-out calls. It refuses calls that would bring reservations above $20. All calls through this provider share the ledger. Do not run multiple evaluation processes concurrently against the ledger.

The estimate uses standard token prices of $5/$30 per million input/output tokens for GPT-5.5, $4/$20 for GPT-5.6 Sol, $5/$25 for Claude Opus 4.8, and $10/$50 for Claude Fable 5. Source pages were checked when the pilot was prepared. Provider billing records remain authoritative.

Successful completed responses are reused when rerunning with the same model and question. Start a new results directory for a changed prompt, corpus, model configuration, or new independent experiment. A separate minimal GPT-5.6 Sol diagnostic was rejected with exhausted credits and produced no usage.

## Run

Configure `.env` with `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`. Keep that file private. `data/` contains gated benchmark material and is excluded from Git.

The saved `pilot.json` targets all four requested models. `pilot-anthropic.json` runs the available Claude portion after OpenAI credits were exhausted.

```sh
PROMPTFOO_PYTHON=/Users/g4singh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
PROMPTFOO_DISABLE_TELEMETRY=1 node_modules/.bin/promptfoo eval \
  -c pilot.json --env-file .env --no-cache --max-concurrency 1 \
  --output results/promptfoo-pilot.json
```

Generate the summary and plot with the Python environment containing Matplotlib.

```sh
/Users/g4singh/.venvs/officeqa/bin/python report_pilot.py
```

The summary distinguishes blocked models from completed evaluations. Only models with all 10 completed question responses are plotted. Costs include diagnostic retries, making them pilot execution costs rather than estimates for an optimized production system.

## Repository setup

Install Node.js and Python 3.10 or newer. Run npm ci, then install matplotlib in your Python environment. Download the gated OfficeQA Pro CSV and source corpus into data/ using your own approved Hugging Face access. The scorer in upstream/ is vendored unchanged, with its source commit and license notices included.

The example run commands document the original Mac environment. Set PROMPTFOO_PYTHON to your Python executable when running elsewhere. In report_pilot.py, update runtime to that executable as well.
