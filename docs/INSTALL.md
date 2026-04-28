# Install & Run

How to set up the review retrievability tool locally and run it on a corpus.

---

## Prerequisites

- Python 3.11 or higher
- An Anthropic API key (sign up at console.anthropic.com)
- ~$1 of API credit for prototyping (a 100-review corpus costs roughly $0.10 with Haiku)

## Setup

### 1. Clone or set up the project directory

```bash
cd /path/to/your/projects/
# either git clone <repo-url> review-tool, or unzip the project
cd review-tool
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate          # macOS/Linux
# OR
venv\Scripts\activate             # Windows
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -e .
```

### 4. Configure your API key

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
```

The `.env` file is gitignored. Never commit it.

### 5. Verify the install

```bash
pytest tests/test_classify.py
```

If this passes, the deterministic parts of the pipeline are working. If not, fix the failures before continuing.

## Running the tool

### Basic invocation

```bash
python -m review_tool.analyze \
    --reviews path/to/reviews.csv \
    --output reports/my_business/
```

This will:
1. Load the reviews
2. Infer the business profile (1 LLM call)
3. Score every review (N LLM calls for N reviews)
4. Classify, aggregate, and write `report.json` + `report.txt` to the output directory

For 100 reviews this takes ~2 minutes and costs ~$0.10 with Haiku.

### With business one-liner

```bash
python -m review_tool.analyze \
    --reviews path/to/reviews.csv \
    --oneliner "Christina Tosi's Milk Bar at the Cosmopolitan, Las Vegas" \
    --output reports/milk_bar/
```

The one-liner is optional but useful for thin or specialty corpora.

### Other useful commands

```bash
# Run all tests (deterministic + LLM-call tests)
pytest

# Run only deterministic tests (fast, no API calls)
pytest -m fast

# Run the labeler against the gold set dev split, see agreement
python tests/evaluate.py \
    --gold tests/fixtures/review_retrievability_gold_v3.json \
    --predictions outputs/labels.json \
    --split dev

# Validate the gold set fixture
python scripts/validate_gold_set.py
```

## Troubleshooting

### `ImportError: No module named 'review_tool'`

You're not in the project root, or the package isn't installed in editable mode. Try:
```bash
cd /path/to/review-tool
pip install -e .
```

### `anthropic.AuthenticationError: Invalid API key`

Check that `.env` exists in the project root and contains `ANTHROPIC_API_KEY=...` with your real key. Make sure there are no quotes around the value and no trailing whitespace.

### `RateLimitError: ...`

You're hitting Anthropic's rate limits. The runtime retries with exponential backoff (1s, 2s, 4s, 8s), but if you're running on very large corpora (1000+ reviews) and still hitting limits, consider:
- Splitting your corpus into smaller files and running them separately
- Upgrading your API tier

### The labeler returns invalid JSON

This should be handled by the runtime (one retry with corrective message; falls back to all-zeros if second attempt fails). If you're seeing it consistently, check `prompts/review_scorer.md` for syntax issues — the prompt may have been edited in a way that confused the model.

### Reports look wrong / numbers don't match

Re-run with the same input. If the numbers shift significantly between runs, your labeler may not be running at temperature=0. Check `review_tool/scorer.py` for the temperature setting.

### Tests fail after a prompt change

Expected. After editing `prompts/review_scorer.md`, the labeler's behavior changes. Re-run `python tests/evaluate.py --split dev` and look at the disagreements. Iterate the prompt until the dev-split bucket agreement is acceptable.

## What "deployment" looks like (and doesn't)

This is a CLI tool. There is no deployment in the web-app sense — no servers, no domain, no hosting. To "deploy" means: install on a machine that has Python 3.11+ and an API key. That's it.

When the prototype is validated and ready for an agency-facing wrapper:
- A web wrapper would call the same CLI as a subprocess, or import the `review_tool` package directly
- That web wrapper is future scope; not part of v1

## Cost estimates (with Claude Haiku 4.5)

Approximate costs at current API pricing. Verify against your actual bills.

| Corpus size | LLM calls | Approximate cost |
|---|---|---|
| 30 reviews | 31 (1 profile + 30 scoring) | ~$0.03 |
| 100 reviews | 101 | ~$0.10 |
| 500 reviews | 501 | ~$0.50 |
| 1000 reviews | 1001 | ~$1.00 |

Sonnet is roughly 12x more expensive per token. Stay on Haiku unless dev-split evaluation shows it's not accurate enough.
