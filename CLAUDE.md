# Review Retrievability Diagnostic — Prototype

## Project

A diagnostic tool that takes a business's existing customer reviews and reports how well-positioned the corpus is to be surfaced by LLM-driven local search (Ask Maps, ChatGPT, Perplexity, Gemini).

**The tool is NOT a quality judgment on reviews.** It is a structural/descriptive analysis of LLM-retrievability. Thin reviews are not "bad" reviews — they just don't contribute to LLM retrieval. Reviews that are descriptively rich are retrievable; reviews that are generic are not, regardless of star rating or sentiment.

**Buyer:** SEO / GEO / AEO agencies who already provide AI-visibility services to local businesses. The tool gives them a measurement layer they currently lack.

**Phase:** Prototype. CLI-only. Validate that the labeler works on real corpora, then build a web wrapper for demos. No production users yet. Ship fast, iterate, no over-engineering.

## Stack

- Python 3.11+
- `anthropic` — Claude API client
- `pandas` — CSV ingestion
- `jsonschema` — runtime validation of LLM outputs
- `typer` — CLI framework
- `pytest` — tests
- `python-dotenv` — environment variable loading

NO web framework, NO database, NO auth. Single-process CLI tool.

## Pipeline

Six stages, each a discrete unit of work. Implement them as separate modules.

1. **Ingest** — load reviews from CSV/JSON, dedup, length filter, language check
2. **Profile inference** — one LLM call over a corpus sample produces structured business profile (services, attributes, customer contexts)
3. **Per-review scoring** — one LLM call per review, returns 5 ordinal dimension scores + relevance flag + confidence + rationale
4. **Classification** — DETERMINISTIC, NOT LLM-decided. Apply the locked bucket rule to dimension scores
5. **Aggregation** — pure arithmetic over per-review classifications. Produces corpus-level stats
6. **Report generation** — full JSON output + deterministic templated human-readable summary. NO second LLM call for the summary

## The Locked Rubric (NON-NEGOTIABLE)

The rubric (five dimensions, 0/1/2 ordinal scale, definitions) and the bucket rule are defined in `docs/SPEC.md` sections 7 and 8. **`SPEC.md` is the single source of truth.** Do not duplicate the rubric here or in any other file — point at SPEC.md instead.

What this means in practice:

- The rubric is **locked.** Five dimensions: `service`, `attributes`, `outcome`, `occasion`, `descriptive_depth`. 0/1/2 ordinal. Three buckets: `service_attribute_matchable`, `trust_quality_matchable`, `low_retrievability`.
- The bucket rule is in `review_tool/classify.py` as `bucket_from_labels()`. Implement it once; reference it everywhere.
- Off-topic reviews (relevance=false from the labeler) always classify as `low_retrievability`, regardless of dimension scores.
- **Outcome fires low (~16%) for consumption businesses.** This is structural, not a labeling failure. The labeler is instructed not to inflate this dimension. Do not "fix" outcome scoring without first checking SPEC.md section 7.
- **Operational attributes weight higher than experiential ones.** "24/7" and "gluten-free" tip attributes to 2; "friendly" and "nice" stay at 1.
- A rubric change requires the four-step process in SPEC.md section 13. Do not change the rubric without doing all four.

## Framing Rules (NON-NEGOTIABLE)

These are the rules that must survive every session. They are easy to violate inadvertently and corrupt the tool's value if violated.

- The tool measures **retrievability**, not quality. Negative reviews can be high-retrievability. Positive reviews can be low-retrievability.
- Output language must always be **structural and descriptive**, never quality-laden. Never say reviews are "good enough" or "bad."
- Headlines describe what the corpus *enables for retrieval*, not what the reviews are *worth*.
- Never label a thin review as a "bad review." It is "low-retrievability" — the customer was happy, the review just doesn't carry semantic content for LLM retrieval.
- Agencies will repeat the tool's language to clients. Every output string is potentially client-facing — keep framing neutral.

## Honesty Rules (NON-NEGOTIABLE)

- The gold set in `tests/fixtures/review_retrievability_gold_v3.json` is **single-labeler synthetic** (produced by Claude). Agreement metrics computed against it are optimistically biased.
- **Never report agreement numbers from this gold set as accuracy claims** in user-facing output, marketing copy, or pitch material. It is for prompt iteration only.
- The README and INPUT_SPEC files document this. Do not remove the caveats.
- When the test set is eventually run for "final" numbers, the result is still bounded by synthetic-labeler ceiling effects.

## Architecture

- Single Python package: `review_tool/`
- CLI entry point: `python -m review_tool.analyze` (or installed as `review-tool`)
- Each pipeline stage is its own module with a clear interface
- Prompts live as `.md` files loaded at runtime — not hardcoded strings in Python
- Schemas live as `.json` files loaded at runtime
- The locked bucket rule is in ONE function (`bucket_from_labels()`) used everywhere
- LLM API calls go through a single client wrapper that handles retries and JSON validation

### File layout

```
review_tool/
├── __init__.py
├── analyze.py            # CLI entry point (typer)
├── ingest.py             # Stage 1: CSV/JSON loading + cleaning
├── profile.py            # Stage 2: business profile inference
├── scorer.py             # Stage 3: per-review labeling
├── classify.py           # Stage 4: bucket rule (deterministic)
├── aggregate.py          # Stage 5: corpus stats
├── report.py             # Stage 6: JSON + templated text output
├── llm_client.py         # Anthropic API wrapper with retry + validation
├── schemas/
│   ├── business_profile.json
│   ├── review_labeler_output.json
│   └── corpus_report.json
└── prompts/
    ├── business_profile.md
    └── review_scorer.md

tests/
├── fixtures/
│   ├── review_retrievability_gold_v3.json   # gold set
│   └── milk_bar_sample.csv                  # unseen test corpus
├── test_ingest.py
├── test_classify.py        # deterministic bucket rule
├── test_aggregate.py       # arithmetic
├── test_labeler_dev.py     # runs labeler on dev split, evaluates
└── evaluate.py             # gold-set comparison

docs/
├── README.md               # project overview + workflow
├── SPEC.md                 # canonical product specification
├── INPUT_SPEC.md           # input file contract
├── INSTALL.md              # setup, run, troubleshoot
├── report-design.md        # output format spec for report.txt + report.json
├── BUILD_LOG.md            # running log of completed features + decisions
├── PROMPT_ITERATION.md     # log of labeler prompt changes
└── edge-cases-tracker.md   # weird inputs and gotchas

scripts/
└── validate_gold_set.py    # gold set integrity check
```

### Doc reference map

When in doubt about something, the canonical source is:
- **What the tool does** → `docs/SPEC.md`
- **What input it accepts** → `docs/INPUT_SPEC.md`
- **What output it produces** → `docs/report-design.md`
- **How to run it** → `docs/INSTALL.md`
- **How we build it** → this file (`CLAUDE.md`)
- **What's been built and what's next** → `docs/BUILD_LOG.md`

## Commands

- `python -m review_tool.analyze --reviews path/to/reviews.csv --output reports/` — run the full pipeline
- `python -m review_tool.analyze --reviews ... --oneliner "Christina Tosi's Milk Bar"` — with optional business description
- `pytest` — run all tests
- `pytest tests/test_classify.py` — single test module
- `python tests/evaluate.py --gold tests/fixtures/review_retrievability_gold_v3.json --predictions outputs/labels.json --split dev` — evaluate labeler against gold
- `python scripts/validate_gold_set.py` — verify gold set integrity

**Always run `pytest` after completing a stage. Fix all failures before moving on.**

## Boundaries on what Claude Code modifies

Some files in this project encode the product's defined behavior. Claude Code should not modify them unilaterally as part of implementation work. If a session believes a change is needed, surface the concern in the response, do not edit.

**Do not modify without explicit instruction from the project owner:**

- The locked rubric (five dimensions, ordinal scale, definitions in this file)
- The bucket rule
- The framing rules
- The prompt files in `review_tool/prompts/` — these encode the labeling logic
- The gold set fixture in `tests/fixtures/`
- The honesty rules and any caveats in `README.md` or `INPUT_SPEC.md`

**Claude Code is responsible for:**

- All implementation (modules, tests, CLI, runtime code)
- Running the pipeline against real corpora
- Iterating on labeler outputs and reporting findings
- Refactoring, debugging, build verification
- Updating `BUILD_LOG.md` after every completed stage

If Claude Code finds during implementation that a locked rule appears wrong or a prompt produces bad outputs, the right response is: report the finding, propose the change, wait for confirmation before editing. Do not "improve" the rubric or prompts as part of unrelated work.

## Rules

- NEVER hardcode prompt strings in Python — load from `prompts/*.md` at runtime
- NEVER hardcode the bucket rule in multiple places — use `bucket_from_labels()` everywhere
- NEVER make a second LLM call for the report summary — it is templated
- NEVER let the LLM decide bucket assignment — it returns dimension scores only
- NEVER inflate the outcome dimension to fill it — 0 is correct for consumption businesses
- NEVER use quality-laden language in user-facing output ("good", "bad", "good enough")
- NEVER claim accuracy/agreement numbers from the synthetic gold set as product validation
- NEVER read or output contents of `.env` files
- NEVER commit the API key
- NEVER use placeholder comments like `# TODO` or `# implement later` — components are complete or not committed
- NEVER use `print()` for diagnostic output — use Python's `logging` module
- ALWAYS validate LLM output against the JSON schema before using it
- ALWAYS retry once on schema validation failure with a corrective message
- ALWAYS run `pytest` after completing a stage; fix all failures before moving on
- ALWAYS use type hints — no `Any` unless genuinely necessary
- ALWAYS handle the case where the corpus is too thin (<20 reviews) — flag in report, do not crash
- ALWAYS use temperature=0 for the labeler (stability matters more than variation)
- ALWAYS preserve original review text — never modify it before showing back to the user

## File Naming

- Python modules: snake_case (`review_scorer.py`, `llm_client.py`)
- Test files: `test_<module>.py` matching the module under test
- Prompts: `<purpose>.md` (`review_scorer.md`, `business_profile.md`)
- Schemas: `<output_type>.json` (`review_labeler_output.json`)
- Fixtures: descriptive name + version (`review_retrievability_gold_v3.json`)

## Testing Approach

Tests are organized by what they verify:

- **`test_classify.py`** — `bucket_from_labels()` is pure arithmetic; test exhaustively across the score space
- **`test_aggregate.py`** — corpus stats are arithmetic; test edge cases (0 reviews, 1 review, all-bucket-3 corpus)
- **`test_ingest.py`** — CSV/JSON loading, dedup, edge cases (empty rows, malformed dates, non-UTF8)
- **`test_labeler_dev.py`** — runs the labeler against the dev split of the gold set, asserts a minimum bucket-agreement threshold (start lenient, tighten over time)
- **No mocking of LLM calls in tests by default.** Use a real Haiku call for the dev-split test; it's cheap and tests the real thing
- **Run `pytest -m fast`** for the deterministic tests only (skips LLM-call tests). Useful during quick iteration

## Current State

See `docs/BUILD_LOG.md` for completed features, decisions made, and next steps. Update it after every stage.

## Quick Reference: Common Workflows

### Start a new session
1. Read `CLAUDE.md` (this file)
2. Read `docs/BUILD_LOG.md` to see what's done and what's next
3. Read the README for context
4. Proceed with the next stage

### Iterate on the labeler prompt
1. Edit `review_tool/prompts/review_scorer.md`
2. Run `python tests/evaluate.py --split dev`
3. Look at "HIGH-CONFIDENCE BUCKET DISAGREEMENTS" — these are real errors to fix
4. Edit prompt; re-run; iterate
5. When satisfied, commit. Note the change in `BUILD_LOG.md`
6. Do NOT run on `--split test` unless doing a final evaluation pass

### Add a new pipeline stage
1. If this changes the pipeline shape (new stage, removed stage, reordered stages), surface the proposal and wait for owner confirmation before implementing
2. Add a new module in `review_tool/`
3. Add tests
4. Run `pytest`; fix failures
5. Update `BUILD_LOG.md`
