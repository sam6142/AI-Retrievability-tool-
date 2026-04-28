# Build Log

Running record of completed work, decisions made, and next steps for the review retrievability tool.

Update after every stage. Newest entries on top.

---

## 2026-04-28 — Session 4.1: HTML report renderer

**Status:** `render_html_report` added to `review_tool/report.py`. `write_report` now emits `report.html` alongside `report.json` and `report.txt`. 584 fast tests passing (571 → 584; 13 new HTML tests).

**Completed:**

- **`review_tool/report.py`** — added:
  - `_HTML_CSS` module-level string constant (inline CSS; pure black/yellow/light-gray palette).
  - `_h()`, `_ha()` — HTML content and attribute escape helpers.
  - `_html_bullet_list()` — `<ul>` from a list of strings.
  - `_chip()` — dimension score chip with `active` class when score ≥ 1.
  - `_svg_bucket_bar(b1, b2, b3, total)` — single stacked-bar SVG. Yellow = SAM, light-gray = TQM, dark-gray = LR. Inline count labels when segment ≥ 70 px wide. `aria-label` for accessibility.
  - `_svg_dimension_bars(dim, weakest)` — five horizontal bars. Yellow fill on #333 track. Weakest dimension label highlighted yellow with `◄` marker.
  - `_html_examples_section(epb, lookup)` — one card per example review: ID, confidence, truncated text, dimension score chips, per-dimension rationale.
  - `render_html_report(report: dict) -> str` — assembles the full self-contained HTML string. No external deps, no JS.
  - Updated `write_report()` to also write `report.html`.

- **`tests/test_report.py`** — 13 new `@pytest.mark.fast` tests:
  - `test_html_starts_with_doctype` — output begins with `<!DOCTYPE html>`
  - `test_html_contains_headline_percentage` — formatted `ai_pct` string present
  - `test_html_framing_no_bad/no_improve/no_good_enough` — framing-rule wording assertions
  - `test_html_svg_bucket_bar_present` / `test_html_svg_dimension_bars_present` — aria-label checks
  - `test_html_svg_rect_elements_present` — `<rect` in output
  - `test_html_all_bucket_names_present` — all three bucket labels
  - `test_html_thin_corpus_note_present/absent_at_20` — thin-corpus boundary
  - `test_html_low_profile_confidence_note_present` — low-confidence note
  - `test_html_example_review_text_appears` — review text in examples section

- **`docs/report-design.md`** — added `## report.html` section documenting layout, style tokens, and implementation reference.

**Decisions:**
- All variable HTML blocks (SVG charts, bullet lists, examples) are pre-rendered before the main f-string template to avoid complex nested expressions in Python 3.11.
- Three-color constraint enforced: yellow (#FFE600), light gray (#EEEEEE), dark gray (#333333) on black (#000000). Dark-gray LR segment uses the same token as borders/dividers — within the palette.
- Inline labels appear in SVG segments only when segment width ≥ 70 px; legend below the bar covers all cases.

**Next: Prompt iteration (Session 4.x)**

---

## 2026-04-28 — Session 3.2: Final integration testing and handoff — PROTOTYPE COMPLETE

**Status:** Prototype complete. All 571 fast tests still passing. Full pipeline validated on Milk Bar (100 reviews). Dev-split agreement re-confirmed at 78.6%. `HANDOFF.md` written.

**Completed:**

- **Full pipeline run on `tests/fixtures/milk_bar_sample.csv`** (100 reviews, `--oneliner "Christina Tosi's Milk Bar"`):
  - Clean exit, 0 reviews dropped after cleaning.
  - Reports written to `reports/milk_bar_final/report.json` and `reports/milk_bar_final/report.txt`.
  - Combined LLM-retrievability: 99.0% (96 SAM + 3 TQM + 1 LR).
  - Business profile: confidence=high, 23 named services, 13 attributes, 7 customer contexts.
  - 429 rate-limit retries occurred (7 retries across 100 calls); all resolved by the LLM client's backoff.
  - Report structure, framing, and wording verified: no quality-laden language, no "good"/"bad"/"improve".

- **Report eyeball findings:**
  - Headline and bucket counts are structurally plausible for a named-product-heavy brand.
  - Outcome coverage at **96%** is confirmed over-scoring (SPEC §7 expects ~12–25% for consumption businesses). Does not affect bucket counts — `outcome` is not in the bucket rule — but distorts the DIMENSION COVERAGE section. Documented in `docs/PROMPT_ITERATION.md`.
  - SAM at 96% is partially genuine for Milk Bar (many trademarked named products: crack pie, cereal milk soft serve, compost cookies). No obviously wrong bucket assignments found by manual review of the 4 LR/TQM reviews.
  - Low-retrievability sample (r_007: "cakes and shakes are unbeatable") — correctly classified: generic category mention, no attributes, no depth.

- **Dev-split evaluation re-run** (`pytest tests/test_labeler_dev.py -m slow -v`):
  - Bucket agreement: **78.6% (77/98)** — 1 pp below v1 baseline (79.6%). Within LLM sampling variance. Test passed (floor 0.75).
  - Same 6 high-confidence disagreements as v1 baseline:
    - r_051 "Best ice cream ever" — service over-scoring (pred SAM, gold LR)
    - r_034 "Chi Tea latte" — service under-scoring (pred LR, gold SAM)
    - r_096 "Every donut was delicious" — service over-scoring (pred SAM, gold LR)
    - r_013 "Mona Lisa everywhere" — attribute under-scoring (pred TQM, gold SAM)
    - u_021 "smooth and well-organized" — depth under-scoring (pred LR, gold TQM)
    - r_019 "Lines are long here" — attribute under-scoring (pred LR, gold SAM)
  - No new patterns. No regression from Session 3.1 code changes.

- **`HANDOFF.md`** — written at project root. Covers: what works end-to-end, dev-split agreement, known labeler issues, cost per run (measured: ~$0.39 per 100 reviews on Haiku 4.5), and next steps.

- **`docs/PROMPT_ITERATION.md`** — updated with Session 3.2 dev-split re-run numbers and Milk Bar outcome over-scoring observation.

**Cost per run (measured):**
- ~3,265 input tokens per scoring call (2,532 system prompt + ~733 user message)
- ~300 output tokens per call (estimated)
- 100 reviews: ~$0.39 total (Haiku 4.5 at $0.80 input / $4.00 output per 1M tokens)
- Scales linearly; profile call adds <$0.01.

**Decisions:**
- 78.6% is within noise of 79.6% at temperature=0. The 1 pp drop (1 review) is not a regression — no code changes since Session 2.4 affect the labeler path.
- 99% retrievability on Milk Bar is not a validation number — the corpus is from a brand with many distinctively named products. Report it as an example output, not a benchmark.
- `HANDOFF.md` left as a flat `.md` file at the project root for easy discovery.

**Prototype summary:**
- Six-stage pipeline: fully functional
- CLI: fully functional
- 571 deterministic tests: all passing
- Dev-split agreement: 78.6% (floor 0.75)
- Cost: ~$0.39 per 100 reviews
- Outstanding: outcome over-scoring in the labeler prompt; TQM bucket weak at 13.3%

**Next: Prompt iteration (Session 4.x)**

Use the 6 high-confidence disagreements to write targeted prompt additions:
1. Negative outcome examples: "it was delicious" → outcome=0
2. TQM example: depth=1, no named service
3. Service tier clarification: generic category vs. trademarked name

---

## 2026-04-27 — Session 3.1: End-to-end polish and edge-case closure

**Status:** All 571 fast tests still passing. Full pipeline validated against a thin corpus. No new features — polish only.

**Completed:**

- **`review_tool/scorer.py`** — Added `_MAX_REVIEW_WORDS = 1500` constant and `_maybe_truncate(review_id, text)` helper. Called in `score_review()` before building the user message. Truncation is pre-emptive (word count check), not reactive (no `BadRequestError` catching needed). Logs a WARNING with the review_id when truncation fires. This closes the edge case "Tokens-too-long error on a single very long review" from `edge-cases-tracker.md`.

- **`review_tool/schemas/review_labeler_output.json`** — Changed `additionalProperties` to `true` on the top-level `ReviewLabelerOutput` object. `DimensionScores` and `Rationale` retain `additionalProperties: false`. This closes the edge case "LLM returns extra fields" — spurious fields (e.g. a `bucket` field the model may echo back) are now silently ignored instead of triggering a retry and fallback.

- **`review_tool/analyze.py`** — Added explicit `except LLMAuthError` handler before the generic `except Exception` catch. Previously, a missing or invalid API key would print a traceback via `logger.exception()`. Now it prints only the friendly message and exits 1 cleanly.

- **`review_tool/aggregate.py`** — Removed dead `NotRequired` import (imported but never used; `total=False` inheritance is used instead).

- **`docs/edge-cases-tracker.md`** — Moved all "anticipated" entries to the "Resolved" section with dates, fixes, and lessons. Every edge case from the original anticipated list is now documented as resolved, including the ones handled via schema enforcement (out-of-range scores, extra fields, 6th dimension hallucination).

- **`docs/INSTALL.md`** — Removed stale `--throttle-ms 200` option reference (that CLI flag was never implemented). Removed the "if pyproject.toml is not yet set up" fallback (pyproject.toml has been in place since Session 1.1). Corrected rate-limit troubleshooting advice to match the actual retry behavior.

- **`tests/fixtures/thin_corpus.csv`** — New 5-review fixture for thin-corpus end-to-end testing. Validated: tool runs to completion, report includes both the HEADLINE thin-corpus NOTE and the BUSINESS PROFILE low-confidence NOTE.

**CLI usability verified (all inputs produce clean exit-1 messages, no tracebacks):**
- Non-existent file: `Error: Reviews file not found: nonexistent.csv`
- Empty CSV: `Error: No reviews found in tests\fixtures\_tmp_empty.csv`
- Wrong column name: `Error: CSV missing required column 'review_text' (found: ['text', 'stars'])`
- Missing API key: `Error: ANTHROPIC_API_KEY is not set. Add it to your .env file...`

**Decisions:**
- Pre-emptive truncation (word count check before the API call) is cleaner than reactive truncation (catching `BadRequestError`). The 1500-word limit is conservative — Haiku's context window is much larger — but the combined payload (system prompt + profile JSON + review) can be substantial.
- `additionalProperties: true` at the envelope level, `false` inside data sub-objects, is the right policy split: be permissive about what the model wraps the data in, be strict about the shape of the data itself.
- Explicit `LLMAuthError` handler avoids the unhelpful traceback that `logger.exception()` would produce for a user-actionable configuration error.

**Next: Session 3.2 — Labeler prompt iteration**

Use the v1 baseline patterns (PROMPT_ITERATION.md) to tighten the labeler. Priority targets:
1. Fix `service` over-scoring for generic product categories ("donut", "ice cream" → service=0)
2. Fix `attributes` under-scoring for operational specifics ("lines are long on weekends" → attributes=2)
3. Add negative bakery example for `outcome` (no problem/resolution arc → outcome=0)
4. Add a TQM example with depth=1 but no named service to improve the 13.3% TQM accuracy

---

## 2026-04-27 — Session 2.4: Phase 2 tests + first dev-split evaluation

**Status:** `tests/test_report.py` and `tests/test_labeler_dev.py` complete. 571 fast tests passing. First dev-split evaluation complete; baseline agreement 79.6%.

**Completed:**

- **`tests/test_report.py`** — 23 deterministic tests (`@pytest.mark.fast`):
  - `build_report`: top-level keys, examples_per_bucket population, all-low-retrievability corpus, schema mismatch raises `ValidationError`, invalid bucket in stats raises `ValidationError`, scored_reviews preserved.
  - `render_text_report` zero-bucket lines: all three bucket count lines render even when a bucket has 0 reviews (b1=0, b2=0, b3=0 each tested).
  - Thin corpus warning: boundary cases at 5, 19, 20, and 25 reviews; warning present at <20, absent at ≥20.
  - Low profile confidence note: appears for confidence="low", absent for "medium" and "high"; includes the word "provisional".
  - Wording rules: `"good enough"`, `"bad"`, and `"improve"` each asserted absent from rendered text.
  - Structural completeness: all six section headers present; review text appears in EXAMPLES; all three bucket labels present even when empty.

- **`tests/test_labeler_dev.py`** — 1 test (`@pytest.mark.slow`):
  - Loads dev split (98 reviews) from `tests/fixtures/review_retrievability_gold_v3.json`
  - Scores each review with `scorer.score_review()` using a hand-crafted bakery profile
  - Saves predictions to `outputs/labels_dev.json`
  - Calls `tests/evaluate.evaluate()` and asserts `bucket_agreement >= 0.75`
  - Skips if `ANTHROPIC_API_KEY` not set

- **`pyproject.toml`** — added `slow` marker registration.

- **First dev-split evaluation run (v1 baseline):**
  - Bucket agreement: **79.6% (78/98)**
  - High-confidence disagreements: **6 (9.8%)**
  - Relevance agreement: **100.0%** (off-topic detection works perfectly)
  - Weakest bucket: `trust_quality_matchable` (only 13.3% correct)
  - Key patterns: labeler over-scores service for generic categories ("donut", "ice cream"), under-scores operational attributes ("lines are long"), outcome fires too often (~0→1 errors)

- **`docs/PROMPT_ITERATION.md`** — filled v1 baseline entry with full metrics, confusion matrix, disagreement analysis, and next-iteration hypotheses.

**Decisions:**
- Slow test skips cleanly on missing API key via `pytest.skip()` rather than crashing; this keeps `pytest` (fast) green in environments without credentials.
- Regression floor set at 0.75 (5 pp below observed 79.6%) to absorb LLM sampling variance while still catching prompt regressions.
- `outputs/` directory created at test runtime; excluded from git via existing `.gitignore`.

**Next: Session 2.5 — Labeler prompt iteration**

Use findings from the v1 baseline to tighten the prompt. Priority targets:
1. Fix `service` over-scoring for generic product categories
2. Fix `attributes` under-scoring for operational specifics
3. Fix `outcome` over-firing with a bakery-specific negative example

---

## 2026-04-27 — Session 2.3: Stage 6 (report generation) + CLI assembly

**Status:** `report.py` and `analyze.py` complete. All 548 deterministic tests still passing.

**Completed:**

- **`review_tool/report.py`**
  - `_pick_examples(scored_reviews, max_per_bucket=3)` — returns up to 3 review_ids per bucket in corpus order, using `BUCKETS` from classify.py as the canonical key list.
  - `build_report(reviews, scored_reviews, business_profile, corpus_stats, metadata) -> dict` — assembles the full `CorpusReport` dict and validates it against `review_tool/schemas/corpus_report.json` via `jsonschema.validate()`. Raises `jsonschema.ValidationError` on schema mismatch.
  - `render_text_report(report) -> str` — deterministic text rendering using the fixed template from `docs/report-design.md`. All wording rules applied (no "good"/"bad"/"good enough"). Conditional sections wired:
    - Thin corpus note (`total_reviews < 20`) prepended after the HEADLINE section header.
    - Low profile confidence note (`confidence == "low"`) appended after the BUSINESS PROFILE section.
  - `write_report(report, output_dir) -> None` — creates output directory if needed, writes `report.json` (2-space indent, UTF-8) and `report.txt` (UTF-8).
  - `_section(title)` helper — produces a section header element (with leading/trailing `\n`) that, when joined into the `lines` list, yields correct blank-line spacing before and after each `────` divider.
  - `_bullet_list`, `_truncate(text, max_len=120)` helpers.

- **`review_tool/profile.py`** — added `sample_size: int = _SAMPLE_SIZE` parameter to `infer_profile()`. Passed through to `_stratify_sample()`. Backward-compatible; all callers that omit it use the default of 30.

- **`review_tool/analyze.py`** — typer CLI entry point.
  - Options: `--reviews` (Path, required), `--output` (Path, required), `--oneliner` (str, optional), `--model` (default `claude-haiku-4-5-20251001`), `--profile-sample-size` (int, default 30).
  - `_count_raw_rows(path)` — quick file peek to count raw rows before ingest cleaning, for the `input_review_count_raw` metadata field.
  - Pipeline prints: `[1/6]` through `[6/6]` stage banners on stdout. Scoring progress via `\r`-based callback printing `(i/N)` in place.
  - Logging configured to stderr (INFO+, `%(levelname)s %(name)s: %(message)s`).
  - Headline summary printed after completion: combined LLM-retrievability % + bucket counts.
  - Error handling: `FileNotFoundError` and `ValueError` print a clean message and exit 1; unexpected errors log the traceback and exit 1.
  - `if __name__ == "__main__": app()` block enables `python -m review_tool.analyze`.

**Decisions:**
- `render_text_report` is called by both `write_report` (for `report.txt`) and `analyze.py` (to print the headline). The double-call is cheap and avoids threading the rendered string through the API.
- Thin corpus note placed at top of HEADLINE content (before the counts), matching "prepend after HEADLINE" in report-design.md. Low confidence note appended at the bottom of BUSINESS PROFILE.
- Labeling confidence percentages computed from `total_reviews` (safe division guards total=0 edge case).
- `_count_raw_rows` duplicates a small amount of ingest logic intentionally — the metadata field requires a count before cleaning, and the ingest function's signature returns only the cleaned list.

**Next: Session 2.4 — tests for scorer + dev-split evaluation harness**

Build `tests/test_labeler_dev.py`: run scorer against the dev split of the gold set, assert a minimum bucket-agreement threshold. Wire the prompt-loading regex into a fast unit test so prompt-file structural breakage is caught without an LLM call.

---

## 2026-04-27 — Session 2.2: Stage 3 (per-review scorer)

**Status:** `scorer.py` complete. All 548 deterministic tests still passing. No tests written this session.

**Completed:**

- **`review_tool/scorer.py`**
  - `_load_system_prompt()` — reads `prompts/review_scorer.md`, extracts the system-prompt fenced block beneath `## System prompt`, then the contents of `## Few-shot examples` up to the next `## ` heading. Strips the file's stray standalone ` ``` ` line (the closing fence with no opening partner near the end of the few-shot section). Concatenates them into a single system prompt; verified output is 9209 chars and ends after Example 6.
  - `_load_schema()` — reads `schemas/review_labeler_output.json`.
  - Both prompt and schema cached in module-level globals after first read so per-review calls don't re-parse them.
  - `_build_user_message(review_text, business_profile)` — matches the user-message template in the prompt file: profile JSON (indent=2, ensure_ascii=False) + `Score this review:` + the review text wrapped in double quotes.
  - `score_review(review, business_profile, model)`:
    - Calls `llm_client.call_with_validation` with the labeler schema, **temperature=0**.
    - Validation/retry logic delegated to the wrapper.
    - Calls `classify.bucket_from_labels(labels, relevance)` to compute the bucket — labeler never decides this.
    - Returns a `ScoredReview` (TypedDict imported from `aggregate`) with `bucket` (NOT `expected_bucket` — that's gold-set-only).
  - `_fallback_scored_review(review)` — all-zero labels, `confidence="low"`, rationale entries reading "scoring failed — fallback to default labels", relevance=True. `bucket_from_labels` deterministically maps this to `low_retrievability`.
  - `score_corpus(reviews, business_profile, model, progress_callback)`:
    - Iterates per review; catches **only** `LLMValidationError` (post-retry) and substitutes the fallback. Auth errors and `RuntimeError` (rate-limit/timeout exhaustion) propagate — they can't be recovered per-review.
    - Logs each fallback at ERROR with review_id and progress index. Logs aggregate fallback count at WARNING after the loop if any failures occurred.
    - `progress_callback(index, total, scored_review)` invoked after each review (1-based index) when provided.

**Decisions:**
- Few-shot examples are loaded as the entire `## Few-shot examples` section text (instructional sentences + Examples 1–6), not just the example bodies. Including the meta-instructions is harmless; carving out only `### Example` subsections would be brittle to prompt edits.
- The orphan ` ``` ` line near the end of the few-shot section in the prompt file is stripped by regex rather than fixed in the prompt — `prompts/` files are out of scope for unilateral edits per CLAUDE.md.
- `_fallback_scored_review` sets `relevance=True`. The bucket is `low_retrievability` either way (all-zero labels), but `True` reflects "we never got an answer" more honestly than asserting an off-topic decision the model didn't actually make.
- Per-review caching of system prompt + schema is module-level (single-process CLI tool, no concurrency concerns).
- Caught exception types are narrow: only `LLMValidationError`. The wrapper's retries already handle transient JSON/schema problems.

**Next: Session 2.3 — Tests for the scorer + dev-split evaluation harness**

Build `tests/test_labeler_dev.py`: run scorer against the dev split of the gold set, assert a minimum bucket-agreement threshold (start lenient). Also wire the prompt-loading regex into a fast unit test so prompt-file structural breakage is caught without an LLM call.

---

## 2026-04-27 — Session 2.1: LLM client wrapper + Stage 2 (business profile inference)

**Status:** `llm_client.py` and `profile.py` complete. All 548 existing tests still passing.

**Completed:**

- **`review_tool/llm_client.py`**
  - Custom exceptions: `LLMAuthError` (auth failures, no retry) and `LLMValidationError` (bad output after retry, carries `.bad_output` attr)
  - `_get_client()` reads `ANTHROPIC_API_KEY` from env (loaded via `python-dotenv`) and raises `LLMAuthError` immediately if absent
  - `_make_api_call()` — single API call with separate backoff counters:
    - `RateLimitError`: exponential backoff 1s/2s/4s/8s, up to 4 retries
    - `APITimeoutError` / `APIConnectionError`: backoff 1s/2s, up to 2 retries
    - `AuthenticationError`: re-raised as `LLMAuthError` immediately
  - `_strip_fences()` — strips ``` ``` ``` or ` ```json ` fences from model output
  - `call_with_validation(system_prompt, user_message, schema, model, temperature, max_tokens)`:
    - Attempt 1: call → strip fences → parse JSON → validate schema → return
    - On JSON or schema failure: append corrective turn (assistant bad output + user correction) and retry once
    - Attempt 2 failure: raise `LLMValidationError` with raw output
    - Default model: `claude-haiku-4-5-20251001`, temperature: 0, max_tokens: 1024

- **`review_tool/profile.py`**
  - `BusinessProfile` TypedDict matching `schemas/business_profile.json`
  - `_load_prompt_blocks()` — reads `prompts/business_profile.md`, extracts both fenced blocks (system prompt + user message template) via regex
  - `_stratify_sample(reviews, n=30)` — sorts by word count, samples at even intervals to guarantee short+long mix
  - `_build_user_message(sample, template, oneliner)` — splits template at `Reviews:`, substitutes `{n}` and `{user_oneliner_or_empty_string}` in the header, then builds the numbered review list dynamically
  - `infer_profile(reviews, oneliner)`:
    - Corpus < 10: severe warning (highly unreliable)
    - Corpus < 20 (edge-cases-tracker threshold): warning + force `confidence = "low"` in result
    - Calls `llm_client.call_with_validation` with the business_profile schema
    - If result confidence is "low": logs warning for downstream report to surface

**Decisions:**
- `max_tokens` added to `call_with_validation` with a default of 1024; signature is a superset of the specified interface
- Corrective retry message includes the specific schema validation error to give the model a precise fix target
- Thin-corpus confidence override (< 20 reviews) is applied after the LLM call, not instead of it — the LLM still gets to run and may return useful partial data

**Next: Session 2.2 — Stage 3 (per-review scorer)**

Build `review_tool/scorer.py`:
- Load prompt from `review_tool/prompts/review_scorer.md`
- One `llm_client.call_with_validation` call per review
- Clamp out-of-range scores to 0–2 with a warning
- Call `classify.bucket_from_labels()` to assign bucket
- Return list of `ScoredReview` dicts

---

## 2026-04-27 — Session 1.3: Tests for deterministic pipeline

**Status:** Ingestion, classification, and aggregation complete. No LLM calls in this session.

**Completed:**

- **`review_tool/ingest.py`** — `ingest(path) -> list[Review]`
  - `Review` TypedDict: `{review_id, text, rating, date}` (`text` is the internal field; input CSV column stays `review_text`)
  - CSV encoding fallback: tries utf-8, latin-1, cp1252 before failing
  - Drops empty text, `#ERROR!`/spreadsheet-error tokens, emoji/punctuation-only rows, reviews under 3 words
  - Deduplicates by exact text match (case-insensitive)
  - Fills blank review_ids with `r_001`, `r_002`, ...; re-generates ALL IDs if any duplicates detected (with warning)
  - Raises `ValueError("No reviews found in {path}")` on empty corpus — does not crash silently
  - Smoke-tested: 100 reviews from both `milk_bar_sample.csv` and `milk_bar_sample.json`

- **`review_tool/classify.py`** — `bucket_from_labels(labels, relevance=True) -> str`
  - Single source of truth for the bucket rule (SPEC.md §7, Stage 4)
  - Off-topic reviews (relevance=False) → `low_retrievability` unconditionally
  - `service≥2 OR attributes≥2` → `service_attribute_matchable`
  - `elif descriptive_depth≥1` → `trust_quality_matchable`
  - else → `low_retrievability`
  - Exports `DIMENSIONS` and `BUCKETS` tuples used by aggregate and downstream

- **`review_tool/aggregate.py`** — `aggregate(scored_reviews) -> CorpusStats`
  - Defines `ScoredReview` and `CorpusStats` TypedDicts (scorer.py will import `ScoredReview` from here)
  - Computes all `CorpusStats` fields: `total_reviews`, `by_bucket`, `ai_visibility_pct`, `dimension_coverage_pct`, `weakest_dimension`, `confidence_distribution`
  - `weakest_dimension` tiebreaker: SPEC rubric order (service → attributes → outcome → occasion → descriptive_depth) — deterministic
  - Raises `ValueError` on empty list (no silent divide-by-zero)
  - Logs warnings for unexpected bucket/confidence values rather than crashing

**Decisions:**
- `ScoredReview` lives in `aggregate.py`; scorer.py will import it from there to avoid a `types.py` outside the spec layout
- `_DIMENSIONS` / `DIMENSIONS` defined once in `classify.py` and imported by `aggregate.py` — rubric is not duplicated

**pyproject.toml fix (pre-session):**
- `build-backend` corrected from `setuptools.backends.legacy:build` → `setuptools.build_meta`
- `pytest` moved from `[project.optional-dependencies].dev` into main `dependencies`

**Post-1.2 fixes to `review_tool/ingest.py` (before Session 1.3):**
- `_resolve_ids`: previously re-generated ALL IDs when any duplicate was found, destroying valid user-provided IDs. Now walks reviews in order; only blank or duplicate-occurrence IDs get an `r_NNN` assignment. Generated IDs skip any `r_NNN` already claimed by a user-provided ID. Logs count of regenerated IDs.
- `_load_json`: extracted `_try_read_json(path) -> str` helper (mirrors `_try_read_csv` pattern) that loops over encodings catching only `UnicodeDecodeError`. `json.loads()` is now called outside the loop; `JSONDecodeError` is wrapped into `ValueError("Cannot parse JSON at {path}: ...")` with correct error attribution.

**Next: Session 1.3 — Tests**

Build `tests/test_ingest.py`, `tests/test_classify.py`, `tests/test_aggregate.py`.
Run `pytest`; fix all failures before moving on.

---

## 2026-04-27 — Session 1.3: Tests for deterministic pipeline

**Status:** 548 tests written and passing. `pytest -m fast` selects all 548 (no LLM tests exist yet).

**Completed:**

- **`pyproject.toml`** — added `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, registered `fast` marker
- **`tests/conftest.py`** — `fixtures_dir` fixture (path to `tests/fixtures/`); `make_scored_review` factory for aggregate tests
- **`tests/test_classify.py`** — 500 tests total:
  - 486 exhaustive parametrized cases: all 3^5=243 score combos × 2 relevance values; expected bucket computed inline from the locked rule
  - 14 named tests for specific SPEC.md §7 cases: service=2 alone, attributes=2 alone, service=1 alone, depth=1 only, all-zeros, relevance=False override, outcome/occasion irrelevance, canonical string values
- **`tests/test_aggregate.py`** — 22 tests:
  - Empty list raises ValueError
  - Single-review corpora for all three buckets
  - Homogeneous all-bucket-1 and all-bucket-3 corpora
  - Mixed corpus: bucket counts, ai_visibility_pct formula, zero/100% visibility
  - Dimension coverage: all-zeros, partial, full
  - weakest_dimension: clear winner, tiebreaker uses SPEC rubric order (service beats attributes on tie)
  - Confidence distribution; empty buckets appear as 0
- **`tests/test_ingest.py`** — 26 tests:
  - Real fixture load: CSV and JSON (95–100 reviews each); shape checks; unique IDs
  - Dedup: exact match dropped, case-insensitive dedup
  - Junk filter: #ERROR!, #N/A, #VALUE!, #REF!, 2-word, 1-word, empty, emoji-only
  - Optional columns: missing rating/date/review_id filled gracefully; extra columns ignored; rating normalised (out-of-range → None)
  - ID assignment: blank → r_001/r_002; user IDs preserved; duplicate IDs → second occurrence regenerated
  - Errors: FileNotFoundError, ValueError("No reviews found"), ValueError("Unsupported file type"), wrong column name, invalid JSON, JSON non-array

**Next: Session 2.1 — LLM client + Stage 2 (business profile)**

---

## 2026-04-27 — Session 1.1: Project scaffold complete

**Status:** Directory structure created; all files in canonical locations. No pipeline code written yet.

**Completed:**
- Created directory tree: `review_tool/`, `review_tool/prompts/`, `review_tool/schemas/`, `tests/`, `tests/fixtures/`, `docs/`, `scripts/`
- Moved prompt files to `review_tool/prompts/` (business_profile.md, review_scorer.md)
- Moved all docs to `docs/` (SPEC, INPUT_SPEC, INSTALL, report-design, BUILD_LOG, PROMPT_ITERATION, edge-cases-tracker)
- Moved fixtures to `tests/fixtures/` (gold set, milk_bar_sample.csv, milk_bar_sample.json)
- Moved `evaluate.py` → `tests/evaluate.py`; `validate_gold_set.py` → `scripts/validate_gold_set.py`
- Split `schemas.json` into three self-contained JSON Schema draft-07 files in `review_tool/schemas/`
- Created `pyproject.toml` with editable-install config and all declared dependencies
- Created `review_tool/__init__.py`, `tests/__init__.py`, `.gitignore`, `.env.example`
- Fixed hardcoded path in `scripts/validate_gold_set.py` to use `pathlib` relative to script location

**Next: Session 1.2 — Stage 1: Ingestion**

Build `review_tool/ingest.py` per the spec in the entry below.

---

## 2026-04-27 — Project setup phase complete

**Status:** No code written yet. Spec phase done.

**Artifacts ready for implementation:**
- `CLAUDE.md` — project context and locked rules
- `docs/README.md` — project overview and workflow
- `docs/SPEC.md` — canonical product specification (rubric, pipeline, framing rules)
- `docs/INPUT_SPEC.md` — input file contract
- `docs/INSTALL.md` — setup, run, troubleshooting
- `docs/report-design.md` — output format spec for report.txt + report.json
- `docs/PROMPT_ITERATION.md` — log scaffold for labeler prompt changes
- `docs/edge-cases-tracker.md` — scaffold of anticipated edge cases + space for new ones
- `review_tool/prompts/business_profile.md` — Stage 2 prompt
- `review_tool/prompts/review_scorer.md` — Stage 3 prompt
- `review_tool/schemas/*.json` — JSON schemas for runtime validation
- `tests/fixtures/review_retrievability_gold_v3.json` — 140-review labeled gold set with dev/test split
- `tests/fixtures/milk_bar_sample.csv` — 100 unseen reviews for end-to-end testing
- `tests/evaluate.py` — labeler-vs-gold evaluation script
- `scripts/validate_gold_set.py` — gold set validator

**Locked decisions:**
- Five-dimension rubric: service, attributes, outcome, occasion, descriptive_depth (0/1/2 ordinal)
- Bucket rule: `service≥2 OR attributes≥2 → bucket 1; elif depth≥1 → bucket 2; else bucket 3`
- Stack: Python 3.11+, anthropic, pandas, jsonschema, typer, pytest, python-dotenv
- Vertical scope: bakery/café/dessert for prototype; service businesses are future scope
- Single-vertical, single-labeler synthetic gold for now; never report agreement numbers as accuracy claims

**Next: Stage 1 — Ingestion**

Build `review_tool/ingest.py`:
- Accepts CSV or JSON file path
- Returns a list of normalized review dicts: `{review_id, text, rating, date}`
- Deduplicates by exact text match
- Filters out reviews <3 words or non-text entries (`#ERROR!` etc.)
- Handles missing optional columns gracefully
- Auto-generates `review_id` if absent

Tests in `tests/test_ingest.py`:
- Loads `milk_bar_sample.csv` cleanly, returns 100 reviews
- Loads `milk_bar_sample.json` cleanly, returns 100 reviews
- Handles a malformed CSV (extra commas, missing columns) without crashing
- Dedups duplicates
- Filters out trivially short or `#ERROR!` rows

Verification: `pytest tests/test_ingest.py` passes.
