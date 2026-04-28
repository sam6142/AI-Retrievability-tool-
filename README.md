# Review Retrievability Diagnostic

A diagnostic tool that takes a business's existing customer reviews and reports how well-positioned the corpus is to be surfaced by LLM-driven local search (Ask Maps, ChatGPT, Perplexity, Gemini).

The tool measures **retrievability**, not quality. A 5-star "great place!" review is low-retrievability. A 2-star review describing a specific bad experience is high-retrievability. The verdict is independent of sentiment.

**Phase:** Prototype. CLI-only. Single vertical (bakery / café / dessert).
**Live demo:** [Sample report on Milk Bar (Las Vegas)](https://sam6142.github.io/AI-Retrievability-tool-/demo/report.html)
---

## Quick start

```bash
# Setup (see docs/INSTALL.md for full instructions)
python3 -m venv venv
source venv/bin/activate
pip install -e .
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# Run on a corpus
python -m review_tool.analyze \
    --reviews tests/fixtures/milk_bar_sample.csv \
    --oneliner "Christina Tosi's Milk Bar at the Cosmopolitan" \
    --output reports/milk_bar/

# Output: reports/milk_bar/report.json + report.txt
```

---

## What's where

| File | Purpose |
|---|---|
| `CLAUDE.md` | Project context for Claude Code sessions — workflow rules, file layout, locked behaviors |
| `docs/SPEC.md` | Canonical product specification — what the tool does, the rubric, the bucket rule |
| `docs/INPUT_SPEC.md` | Input file contract (CSV / JSON shape) |
| `docs/INSTALL.md` | Setup, run, troubleshooting |
| `docs/report-design.md` | Output format spec for `report.json` and `report.txt` |
| `docs/BUILD_LOG.md` | Running log of completed work and next steps |
| `docs/PROMPT_ITERATION.md` | Log of labeler-prompt changes and dev-split agreement deltas |
| `docs/edge-cases-tracker.md` | Anticipated edge cases and resolved gotchas |
| `review_tool/prompts/business_profile.md` | Stage 2 prompt — business profile inference |
| `review_tool/prompts/review_scorer.md` | Stage 3 prompt — per-review labeler |
| `review_tool/schemas/` | JSON schemas for runtime output validation |
| `tests/fixtures/review_retrievability_gold_v3.json` | Labeled gold set (140 reviews, dev/test split) |
| `tests/fixtures/milk_bar_sample.csv` | Unseen test corpus (100 Yelp reviews) |
| `tests/evaluate.py` | Compares labeler predictions to gold labels |
| `scripts/validate_gold_set.py` | Gold set integrity check |

When in doubt about something, the canonical source is:
- **What the tool does** → `docs/SPEC.md`
- **What input it accepts** → `docs/INPUT_SPEC.md`
- **What output it produces** → `docs/report-design.md`
- **How to run it** → `docs/INSTALL.md`
- **How we build it** → `CLAUDE.md`

---

## Development workflow

### Iterating on the labeler prompt

The labeler prompt is the heart of the product. Iteration loop:

1. Edit `review_tool/prompts/review_scorer.md`
2. Run the labeler over the dev split:
   ```bash
   python -m review_tool.label_eval --split dev --output outputs/labels.json
   ```
3. Compare to gold:
   ```bash
   python tests/evaluate.py \
       --gold tests/fixtures/review_retrievability_gold_v3.json \
       --predictions outputs/labels.json \
       --split dev
   ```
4. Look at the **HIGH-CONFIDENCE BUCKET DISAGREEMENTS** section. Each one is a real labeler error to fix.
5. Edit prompt, re-run, iterate.
6. Log the change in `docs/PROMPT_ITERATION.md`.
7. Only run on `--split test` when doing a final evaluation. Do not iterate against test.

### Disagreement interpretation

- *Disagreement on **high-confidence** gold labels* = real labeler error. Fix the prompt.
- *Disagreement on **low-confidence** gold labels* = expected rubric ambiguity. Don't chase these.
- *Disagreement on **medium-confidence** gold labels* = judgment call. Decide case-by-case.

### Adding a pipeline stage

1. If it changes the pipeline shape, surface the proposal first; don't implement unilaterally.
2. Add the module to `review_tool/`.
3. Add tests in `tests/`.
4. Run `pytest`; fix failures.
5. Update `BUILD_LOG.md`.

---

## About the gold set

The gold set in `tests/fixtures/` is **single-labeler synthetic** — produced by Claude. Agreement metrics computed against it are optimistically biased (the model that produced the labels is also the model being evaluated).

This makes the gold set **useful for prompt iteration**, not for accuracy claims. Specifically:

✓ Useful for catching gross labeler failures, surfacing rubric ambiguities, regression-testing prompt changes
✗ Not useful for reporting accuracy numbers in pitches, marketing, or external claims

When the prototype is validated and ready for external claims, replace this gold set with human-labeled data.

The gold set is split 70/30 into dev/test. Dev is for iteration; test is for final evaluation only.

---

## Honesty notes

This is a prototype. A few things to be straight about:

- **Single vertical:** bakery / café / dessert. The rubric's behavior on service businesses (dental, salon, plumbing, automotive) is untested.
- **Single labeler:** Claude produced both the gold labels and the labels being evaluated against them. Agreement is upper-bounded by this.
- **No external validation:** the bucket assignments are a structured opinion, not a ground truth verified against actual LLM retrieval behavior on Ask Maps / ChatGPT / Perplexity.
- **Inflated headline numbers expected:** AI-visibility percentages on real corpora will skew high in this dataset (bakery customers write descriptively). On a typical small business with 50 short reviews, the number will land lower.

---

## License & contact

(To be added.)
