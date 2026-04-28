# Edge Cases Tracker

Running record of weird inputs, failure modes, and gotchas hit during implementation. Append entries as they're discovered.

Use the format:

```
## YYYY-MM-DD — Short title

**What happened:** Brief description of the input or behavior.
**Where:** Module / function / pipeline stage.
**Cause:** Root cause if known.
**Fix:** How it was resolved (or "deferred — see issue #X").
**Lesson:** What to remember for future code.
```

---

## Known edge cases to handle (anticipated, not yet hit)

*(none — all anticipated cases are resolved; see Resolved section below)*

---

## Resolved

---

### 2026-04-27 — Empty review text

**What happened:** CSV rows with blank or whitespace-only `review_text`.
**Where:** `ingest._is_junk()`
**Cause:** Scrapers sometimes produce empty rows.
**Fix:** `_is_junk()` strips text and returns `True` on empty string; dropped rows are counted and logged at INFO.
**Lesson:** Always filter before any downstream processing; log the count so operators can see how many rows were lost.

---

### 2026-04-27 — `#ERROR!` content from broken Yelp scrapes

**What happened:** Cells containing spreadsheet error tokens (`#ERROR!`, `#N/A`, `#DIV/0!`, etc.).
**Where:** `ingest._is_junk()`
**Cause:** Copy-paste from Google Sheets or Excel preserves error cell values.
**Fix:** `_SPREADSHEET_ERROR` regex matches `^#[\w/!?]+$`; matched rows dropped and counted.
**Lesson:** Spreadsheet export artifacts are common in agency-sourced data.

---

### 2026-04-27 — Non-UTF-8 encoding

**What happened:** CSV or JSON file encoded in latin-1 or cp1252 (common in Windows-exported Excel files).
**Where:** `ingest._try_read_csv()`, `ingest._try_read_json()`
**Cause:** Windows Excel defaults to system locale encoding.
**Fix:** Both loaders try utf-8 → latin-1 → cp1252 in order; raise `ValueError` only after all fail.
**Lesson:** Always try the common fallback encodings before failing.

---

### 2026-04-27 — Missing optional columns

**What happened:** CSV without `rating`, `date`, or `review_id` columns.
**Where:** `ingest._load_csv()`
**Cause:** Minimal scrapers only export review text.
**Fix:** `row.get("column", "")` with downstream `None` normalisation; only `review_text` is required.
**Lesson:** Make every column except the primary data optional.

---

### 2026-04-27 — Extra columns

**What happened:** CSV with columns like `source`, `language`, `reviewer_name` beyond the spec.
**Where:** `ingest._load_csv()`
**Cause:** Agencies export richer data than the tool needs.
**Fix:** Only known column names are accessed; extra columns are silently ignored.
**Lesson:** Access by name, not by position; ignore the rest.

---

### 2026-04-27 — Single-row CSV

**What happened:** CSV with exactly one data row.
**Where:** `ingest.ingest()`
**Cause:** Edge case; small test files.
**Fix:** No special-case needed — all paths work on a list of length 1.
**Lesson:** Not a special case.

---

### 2026-04-27 — Empty file / no reviews after cleaning

**What happened:** CSV file with only a header row, or all rows filtered out as junk.
**Where:** `ingest.ingest()`
**Cause:** Empty file or all-junk corpus.
**Fix:** `ingest()` raises `ValueError("No reviews found in {path}")` after cleaning; CLI catches it and exits 1 with a clean message.
**Lesson:** Explicit error, not silent empty list.

---

### 2026-04-27 — Duplicate review_ids

**What happened:** CSV where the same `review_id` appears on multiple rows.
**Where:** `ingest._resolve_ids()`
**Cause:** Scraper bug or manual data merging.
**Fix:** `_resolve_ids()` walks reviews in order; only blank or already-seen IDs get a generated `r_NNN`. Unique user-provided IDs are preserved. Logs a warning with the count of regenerated IDs.
**Lesson:** Walk once and resolve conflicts in order rather than re-generating everything.

---

### 2026-04-27 — Reviews under 3 words

**What happened:** Rows like "Good." or "Love it" — too short to carry retrieval signal.
**Where:** `ingest._is_junk()`
**Cause:** Common on platforms that allow star-only or one-word reviews.
**Fix:** `len(stripped.split()) < 3` check in `_is_junk()`.
**Lesson:** These are not errors; they're legitimate reviews that happen to be uninformative.

---

### 2026-04-27 — Reviews that are entirely emoji or punctuation

**What happened:** Rows like "🎂🎉👍" with no alphanumeric characters.
**Where:** `ingest._is_junk()`
**Cause:** Mobile users sometimes post emoji-only reviews.
**Fix:** `_HAS_ALNUM` regex check in `_is_junk()` — no alphanumeric character → junk.
**Lesson:** Treat as a subcase of "under 3 words"; the word-count check alone doesn't catch these because emoji are single tokens.

---

### 2026-04-27 — Very long reviews (>1500 words)

**What happened:** Occasional reviews that are actually blog posts or copied articles.
**Where:** `scorer._maybe_truncate()`
**Cause:** Some platforms allow very long free-text entries; combined with the system prompt and profile JSON these can exceed the model's context window.
**Fix:** `_maybe_truncate()` checks word count before building the user message; truncates to 1500 words and logs a WARNING with the review_id. Truncation happens before the API call, not as a recovery from an error.
**Lesson:** Pre-emptive truncation is cleaner than catching a `BadRequestError` mid-corpus.

---

### 2026-04-27 — Mixed-language reviews

**What happened:** Non-English reviews in a corpus.
**Where:** `ingest.ingest()`, `scorer.score_review()`
**Cause:** Multi-lingual customer base.
**Fix:** Kept as-is; the labeler handles them (Haiku is multilingual). No special handling needed in v1.
**Lesson:** Not a special case for the prototype vertical.

---

### 2026-04-27 — LLM returns invalid JSON

**What happened:** Model output is not parseable JSON (prose response, truncated, etc.).
**Where:** `llm_client.call_with_validation()`
**Cause:** Model occasionally doesn't follow the JSON-only instruction.
**Fix:** First attempt failure → append corrective turn ("Return only a JSON object...") and retry once. Second failure → raise `LLMValidationError`. In `score_corpus`, `LLMValidationError` is caught and falls back to all-zeros / `low_retrievability`.
**Lesson:** One corrective retry is sufficient; after that, fallback rather than aborting the run.

---

### 2026-04-27 — LLM returns extra fields

**What happened:** Model includes fields like `"bucket"` or `"explanation"` not in the schema.
**Where:** `review_tool/schemas/review_labeler_output.json`
**Cause:** Some prompts cause the model to mirror back computed fields or add prose fields.
**Fix:** `additionalProperties: true` on the top-level `ReviewLabelerOutput` object; extra fields are silently ignored. `DimensionScores` and `Rationale` sub-objects retain `additionalProperties: false` since their shape is tightly constrained.
**Lesson:** Be permissive at the envelope level; be strict inside the data objects that feed computation.

---

### 2026-04-27 — LLM hallucinates a 6th dimension

**What happened:** Model adds a `"tone"` or `"sentiment"` key to the `labels` object.
**Where:** `review_tool/schemas/review_labeler_output.json`
**Cause:** Prompt exposure to sentiment analysis patterns.
**Fix:** `DimensionScores` has `additionalProperties: false`; extra keys in `labels` fail validation → corrective retry → fallback if still present.
**Lesson:** Keep `additionalProperties: false` on data sub-objects to catch structural drift.

---

### 2026-04-27 — Out-of-range scores (e.g., 3 or -1)

**What happened:** Model returns `"service": 3` or `"outcome": -1`.
**Where:** `review_tool/schemas/review_labeler_output.json`
**Cause:** Model loses track of the 0/1/2 ordinal constraint.
**Fix:** `DimensionScores` uses `"enum": [0, 1, 2]` on each dimension. Out-of-range values fail schema validation → corrective retry → `LLMValidationError` → fallback to all-zeros. This is more conservative than clamping but simpler to reason about.
**Lesson:** `enum` constraints are strict; the fallback path handles the rare case where the model ignores them after one correction.

---

### 2026-04-27 — Rate limit / 429 errors

**What happened:** API returns rate limit error during scoring.
**Where:** `llm_client._make_api_call()`
**Cause:** High-volume runs.
**Fix:** Exponential backoff: waits 1s, 2s, 4s, 8s across up to 4 retries. Raises `RuntimeError` after exhaustion (propagates up to abort the run).
**Lesson:** Separate retry counters for rate-limit vs. timeout — they have different characteristics.

---

### 2026-04-27 — API timeout / connection error

**What happened:** API call hangs or TCP connection drops.
**Where:** `llm_client._make_api_call()`
**Cause:** Network instability or slow API response.
**Fix:** Up to 2 retries with 1s, 2s backoff. Raises `RuntimeError` after exhaustion.
**Lesson:** Fewer retries than rate-limit; transient timeouts usually resolve in one retry.

---

### 2026-04-27 — Authentication failure

**What happened:** `ANTHROPIC_API_KEY` is missing or expired.
**Where:** `llm_client._get_client()`, `llm_client._make_api_call()`
**Cause:** Missing `.env` file or expired key.
**Fix:** `_get_client()` raises `LLMAuthError` immediately if the key is absent. `_make_api_call()` catches `anthropic.AuthenticationError` and re-raises as `LLMAuthError`. `analyze.main()` catches `LLMAuthError` explicitly and prints a clean message with exit 1 — no traceback.
**Lesson:** Auth errors are not retriable; fail immediately with a clear actionable message.

---

### 2026-04-27 — Corpus too thin (<20 reviews)

**What happened:** User runs the tool on a small corpus.
**Where:** `profile.infer_profile()`, `report.render_text_report()`
**Cause:** Small business with few reviews, or user testing with a subset.
**Fix:** `infer_profile()` warns at <10 (severe) and <20 (soft), and overrides `confidence` to `"low"` deterministically. `render_text_report()` prepends a thin-corpus NOTE to the HEADLINE section when `total_reviews < 20`.
**Lesson:** Two thresholds: "unreliable" (<10) vs. "low confidence" (<20). The report always runs to completion.

---

### 2026-04-27 — Profile has empty arrays for services / attributes

**What happened:** Generic corpus where no specific services or attributes could be inferred.
**Where:** `report._bullet_list()`
**Cause:** Very thin or very generic corpus.
**Fix:** `_bullet_list([])` returns `"  (none identified)"`. The report section renders gracefully.
**Lesson:** Always render the section; never omit it.

---

### 2026-04-27 — Bucket count is 0

**What happened:** All reviews fall into one bucket, leaving the other two at 0.
**Where:** `report.render_text_report()`
**Cause:** Very homogeneous corpus.
**Fix:** All three bucket lines always render, even with count=0. Zero-count lines tested explicitly in `test_report.py`.
**Lesson:** Never omit a line because the number is zero.

---

### 2026-04-27 — Examples can't be drawn (bucket has 0 reviews)

**What happened:** The EXAMPLES section needs to show a sample for a bucket that has no reviews.
**Where:** `report.render_text_report()`
**Cause:** Same as bucket count = 0.
**Fix:** `"(no reviews in this bucket)"` rendered when the example list is empty. Never crashes.
**Lesson:** Same as above — always render the section.
