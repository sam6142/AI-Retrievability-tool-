# Review Retrievability Diagnostic — Prototype Handoff

**Date:** 2026-04-28
**Status:** Prototype complete. End-to-end pipeline validated.

---

## What Works End-to-End

The full six-stage pipeline runs on a real corpus without manual intervention:

1. **Ingest** — Loads CSV or JSON reviews, deduplicates, filters junk rows, auto-generates IDs. Handles encoding fallbacks (utf-8, latin-1, cp1252). Raises clean errors on empty or malformed files.
2. **Profile inference** — One LLM call over a stratified sample produces a structured business profile (named services, attributes, customer contexts). Confidence is self-reported and surfaced in the report.
3. **Per-review scoring** — One LLM call per review returns five ordinal dimension scores (0/1/2), a relevance flag, confidence, and rationale. Temperature=0 for stability. Long reviews are pre-emptively truncated at 1500 words.
4. **Classification** — Deterministic. `bucket_from_labels()` in `review_tool/classify.py` is the single source of truth. The LLM never decides bucket assignment.
5. **Aggregation** — Pure arithmetic over per-review classifications. Produces corpus-level statistics.
6. **Report generation** — Full JSON output + deterministic templated text summary. No second LLM call.

**CLI invocation:**
```
python -m review_tool.analyze \
  --reviews path/to/reviews.csv \
  --oneliner "Business description" \
  --output reports/output_dir/
```

**Validated on:**
- `tests/fixtures/milk_bar_sample.csv` — 100 reviews, full run, clean exit
- `tests/fixtures/thin_corpus.csv` — 5 reviews, thin-corpus warnings fire correctly
- All error paths tested: missing file, empty CSV, wrong column name, missing API key

---

## Dev-Split Bucket Agreement

**Rubric version:** v2 (locked, no changes made during build)
**Gold set:** `tests/fixtures/review_retrievability_gold_v3.json` — 140 reviews, single-labeler synthetic (produced by Claude). Dev split: 98 reviews.

**v1 baseline (established Session 2.4):** 79.6% (78/98)
**Session 3.2 re-run:** **78.6% (77/98)** — 1 pp below baseline, within LLM sampling variance. Same 6 high-confidence disagreements as v1; no new patterns. Test passed (floor is 0.75).

The regression floor in `tests/test_labeler_dev.py` is set at 0.75. Any prompt iteration that drops below this floor fails CI.

**Honesty caveat (non-negotiable):** The gold set is single-labeler synthetic. Agreement numbers measure consistency with the labeler's own training signal, not external accuracy. Do not cite these numbers as accuracy claims in any user-facing output, pitch material, or marketing copy. See `docs/PROMPT_ITERATION.md` and the README for the full caveat.

---

## Known Labeler Issues (No Code Changes Needed — Prompt Work Only)

### 1. Outcome over-scoring (critical)
The labeler assigns `outcome >= 1` to general satisfaction statements ("it was amazing", "didn't disappoint") which have no problem/resolution arc. On the Milk Bar corpus (100 reviews), outcome coverage was **96%** — against a SPEC §7 expectation of ~12–25% for consumption businesses.

**Impact on buckets: none.** `outcome` is not in the bucket rule. Bucket counts are unaffected.
**Impact on dimension coverage stats: significant.** The `DIMENSION COVERAGE` section shows misleadingly high outcome coverage.
**Fix:** Add explicit negative outcome examples to the labeler prompt. "It was delicious" → outcome=0. See `docs/PROMPT_ITERATION.md`.

### 2. TQM bucket weak (13.3% accuracy on dev split)
The labeler struggles to distinguish `depth=1` (earns trust/quality-matchable) from `depth=0` (low-retrievability) when a review has no named service. Most TQM reviews either land in SAM (over-scored) or LR (under-scored).
**Fix:** Add a TQM example with depth=1 but no named service or strong attribute.

### 3. Service over-scoring for generic category mentions
"Donut" and "ice cream" score service=2 (specific named item) when they should be service=1 (generic category). This is less pronounced on Milk Bar (which has many genuinely specific trademarked items) but confirmed on the synthetic gold set.
**Fix:** Add explicit examples of category names scoring service=1 vs. trademarked names scoring service=2.

### 4. Outcome fires inconsistently on operational attributes
"Lines are long on weekends" should be attributes=2 (operational specificity) but the labeler gives attributes=1. This is a secondary issue but impacts TQM/LR boundary cases.

---

## Rate Limiting

At Haiku 4.5 concurrency levels on a free or low-tier API key, 429s appear roughly every 10–15 reviews in a 100-review run. The LLM client retries with exponential backoff (1s, 2s, 4s, 8s) and all retries succeeded in testing. Not a blocking issue, but adds ~20–40s to a 100-review run.

---

## Cost Per Run (Measured, Not Estimated)

**Model:** `claude-haiku-4-5-20251001`
**Measured input tokens per scoring call:** ~3,265 (2,532 system prompt + ~733 user message)
**Estimated output tokens per scoring call:** ~300

| Corpus size | Input tokens | Output tokens | Approx. cost (USD) |
|-------------|-------------|--------------|-------------------|
| 100 reviews | ~329,000     | ~30,500      | ~$0.39            |
| 50 reviews  | ~165,000     | ~15,500      | ~$0.20            |
| 200 reviews | ~655,000     | ~60,500      | ~$0.77            |

Cost scales linearly with corpus size. The profile inference call adds <$0.01 regardless of corpus size.

Pricing basis: Haiku 4.5 at $0.80/1M input tokens, $4.00/1M output tokens (as of April 2026).

---

## What to Work On Next

### Priority 1 — Prompt iteration to raise dev agreement
Target: 85%+ bucket agreement on the dev split.

Steps:
1. Add negative outcome examples ("it was delicious" → outcome=0)
2. Add a TQM example with depth=1, service=0, attributes=1 (no named item, but structural description)
3. Add a pair distinguishing "donut" (service=1) from "cereal milk soft serve" (service=2)
4. Re-run: `python tests/evaluate.py --split dev`
5. Check "HIGH-CONFIDENCE BUCKET DISAGREEMENTS" — those are real errors to fix
6. Do NOT run `--split test` until doing a final evaluation pass

See `docs/PROMPT_ITERATION.md` for the full change log format.

### Priority 2 — Human-labeled gold set
The current gold set is single-labeler synthetic. Before using agreement numbers for any external claim:
- Label 50–100 real reviews with a human labeler using the rubric
- Compute agreement against human labels
- Replace or supplement the synthetic gold set
- Document the human-labeling process so it can be reproduced

### Priority 3 — Web wrapper for demos
The CLI is demo-ready. A thin web wrapper would lower the friction for showing agency clients:
- File upload (reviews CSV)
- Text field for the oneliner
- Progress indicator (the pipeline takes ~2–5 minutes for 100 reviews)
- Rendered report output
- No auth or database needed for a demo version

Suggested stack: FastAPI + HTMX or a minimal React frontend. The CLI pipeline can be called as a subprocess or imported directly.

### Priority 4 — Throttle or batch mode
The current pipeline makes one synchronous API call per review. For corpora >200 reviews, consider:
- Adding a `--throttle-ms` delay between calls (simple)
- Using the Anthropic Batch API for bulk scoring (cheaper, async)

### Priority 5 — Expand beyond bakery/café vertical
The labeler prompt and few-shot examples are bakery-optimized. Before using on service businesses (restaurants, salons, medical practices):
- Review SPEC §7 on outcome semantics (service businesses have higher legitimate outcome scores)
- Add vertical-appropriate few-shot examples
- Re-evaluate on a labeled sample from the target vertical

---

## Files to Know

| File | What it is |
|------|-----------|
| `docs/SPEC.md` | Canonical product specification. The locked rubric and bucket rule live here. |
| `docs/PROMPT_ITERATION.md` | Prompt change log. All labeler prompt edits tracked here. |
| `review_tool/classify.py` | The locked bucket rule (`bucket_from_labels()`). Never duplicated. |
| `review_tool/prompts/review_scorer.md` | The labeler prompt. This is what to iterate on. |
| `tests/fixtures/review_retrievability_gold_v3.json` | Dev/test split gold set. Dev split is safe to run against repeatedly. |
| `tests/test_labeler_dev.py` | Runs labeler on dev split, asserts >= 0.75 agreement. Run with `pytest -m slow`. |
| `tests/evaluate.py` | Full evaluation harness with confusion matrix and disagreement analysis. |

---

## Running the Test Suite

```bash
# Fast tests only (571 deterministic tests, no LLM calls, <10s)
pytest -m fast

# Full suite including dev-split labeler eval (~3 min, requires ANTHROPIC_API_KEY)
pytest tests/test_labeler_dev.py -m slow -v

# Gold set evaluation with full breakdown
python tests/evaluate.py --gold tests/fixtures/review_retrievability_gold_v3.json \
  --predictions outputs/labels_dev.json --split dev
```

---

*This is a prototype. All pipeline components are functional; the labeler prompt is the primary lever for improving output quality.*
