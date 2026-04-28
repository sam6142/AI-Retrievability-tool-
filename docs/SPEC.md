# Specification — Review Retrievability Diagnostic

The canonical reference for what this tool does. If `CLAUDE.md` is "how we build it," this document is "what it is." When in doubt about behavior, this file is authoritative.

---

## 1. Purpose

Take a business's existing customer reviews. Report how well-positioned the corpus is to be surfaced by LLM-driven local search (Ask Maps, ChatGPT, Perplexity, Gemini) when a user queries for specific services, attributes, or trust signals.

The tool measures **retrievability**, not quality. A 5-star review of "great place!" is low-retrievability. A 2-star review describing a specific bad experience is high-retrievability. The tool's verdict is independent of sentiment.

## 2. Buyer

SEO / GEO / AEO agencies that already provide AI-visibility services to local businesses. The tool is a measurement layer they currently lack.

## 3. Scope

**In scope (v1 prototype):**
- Bakery / café / dessert businesses
- CSV or JSON input of reviews
- CLI interface
- Single-business analysis (one corpus per run)

**Out of scope (deferred to future versions):**
- Service businesses (dental, salon, plumbing, automotive)
- Vertical-specific dimension weighting or rubrics
- Prompt prescription library (recommendations for what to ask customers to write)
- Google Business Profile API integration
- Trained core model — the LLM labeler IS the engine for v1
- Agency dashboard / web UI
- Multi-business portfolio analysis
- Time-series tracking (corpus changes over time)

## 4. Input

Defined formally in `INPUT_SPEC.md`. Summary:

**Required:** A CSV or JSON file of reviews. One field is required per review (`review_text`); rating, date, and review_id are optional.

**Optional:** A free-text one-liner describing the business (~5–30 words). Improves business profile inference for thin or specialty corpora.

The tool does NOT take: business URLs, Google Place IDs, vertical/category selection, pre-classified reviews, or rubric overrides.

## 5. Output

Two files written to the user-specified output directory:

**`report.json`** — machine-readable structured output. Schema defined in `review_tool/schemas/corpus_report.json`. Contains:
- The inferred business profile
- Per-review records: dimension scores, relevance, confidence, rationale, bucket assignment
- Corpus-level rollup: total reviews, bucket counts, AI-visibility percentage, per-dimension coverage, weakest dimension

**`report.txt`** — human-readable templated summary. Format defined in `report-design.md`. Agency-facing language; meant to be readable and quotable to clients.

Both are deterministic outputs from the per-review labels. No second LLM call generates the summary.

## 6. Pipeline

Six stages. Each is a separate Python module.

### Stage 1: Ingest

**Module:** `review_tool/ingest.py`
**Function signature (informal):** `ingest(path: Path) -> list[Review]`

- Loads CSV or JSON (auto-detected from extension)
- Normalizes to a list of `Review` objects: `{review_id, text, rating, date}`
- Auto-generates `review_id` (`r_001`, `r_002`, ...) if absent
- Drops reviews with empty text or `#ERROR!` content
- Drops reviews under 3 words
- Deduplicates by exact text match
- Returns the cleaned list

Edge cases that must not crash: missing optional columns, malformed rows, mixed encodings, empty file, single-row file.

### Stage 2: Business profile inference

**Module:** `review_tool/profile.py`
**LLM call:** 1 call total (not per review)
**Prompt:** `review_tool/prompts/business_profile.md`
**Output schema:** `review_tool/schemas/business_profile.json`

- Takes a stratified sample of ~30 reviews (mix of short and long)
- Optionally takes the user's one-liner description
- Calls Haiku to produce a structured profile: business type, inferred services, attributes, customer contexts, confidence, notes
- Validates output against the JSON schema
- If confidence is "low," the downstream report flags this — the user is told the corpus is too thin to characterize the business reliably

### Stage 3: Per-review scoring

**Module:** `review_tool/scorer.py`
**LLM call:** 1 call per review (N total for N reviews)
**Prompt:** `review_tool/prompts/review_scorer.md`
**Output schema:** `review_tool/schemas/review_labeler_output.json`
**Temperature:** 0

For each review, the labeler returns:
- Five dimension scores (0/1/2 ordinal): `service`, `attributes`, `outcome`, `occasion`, `descriptive_depth`
- A relevance flag (boolean) — false if the review is off-topic
- A self-reported confidence (high / medium / low) — calibrated to per-review labelability
- A one-line rationale per dimension

The labeler does NOT assign buckets. It only scores dimensions. Bucket assignment happens in Stage 4.

### Stage 4: Classification

**Module:** `review_tool/classify.py`
**Function:** `bucket_from_labels(labels: dict) -> str`

Pure deterministic rule. No LLM involvement.

```python
if labels["service"] >= 2 or labels["attributes"] >= 2:
    return "service_attribute_matchable"
elif labels["descriptive_depth"] >= 1:
    return "trust_quality_matchable"
else:
    return "low_retrievability"
```

This is the single source of truth for the bucket rule. It is used by the runtime, by the gold set validator, and by the evaluation script. Do not duplicate it elsewhere.

**Off-topic reviews (relevance=false):** Reviews flagged as off-topic by the labeler in Stage 3 always classify as `low_retrievability`, regardless of dimension scores. They are still counted in `total_reviews` and contribute to `confidence_distribution`, but they do not contribute meaningfully to retrieval. The validator enforces this rule on the gold set, and the runtime should enforce it too — apply the relevance check before the bucket rule.

### Stage 5: Aggregation

**Module:** `review_tool/aggregate.py`

Pure arithmetic over the classified reviews. Computes:
- `total_reviews`
- `by_bucket` — count in each of the three buckets
- `ai_visibility_pct` — `(bucket_1 + bucket_2) / total * 100`
- `dimension_coverage_pct` — for each dimension, the percent of reviews scoring ≥1
- `weakest_dimension` — the dimension with lowest coverage
- A list of representative reviews per bucket (e.g., 3 examples each)

### Stage 6: Report generation

**Module:** `review_tool/report.py`

Produces `report.json` (structured, full content) and `report.txt` (templated summary). Format for the text report defined in `report-design.md`. No LLM call. Pure string formatting over the aggregate stats.

## 7. The Locked Rubric

Five dimensions, 0/1/2 ordinal scale.

### service — names a specific service or product
- **0** = nothing named
- **1** = generic category only ("pastries", "coffee", "service") — does not anchor a query
- **2** = specific named item ("salted caramel brownie", "same-day crown")

### attributes — qualities of experience or place
- **0** = none
- **1** = generic adjectives ("friendly", "nice", "good")
- **2** = specific concrete attributes, **especially operational** (24/7, free wifi, gluten-free, $1.50 prices, no indoor seating). Operational attributes weight higher than experiential ones — when in doubt between 1 and 2, presence of operational specifics tips to 2.

### outcome — what was accomplished or resolved
- **0** = no outcome described
- **1** = mentioned generically ("left satisfied")
- **2** = specific outcome ("first dental visit in 10 years that didn't leave me shaking")

NOTE: Fires low (~16%) for consumption businesses (bakery, café, ice cream). This is structural, not a labeling failure. The labeler is instructed not to inflate this dimension.

### occasion — context of visit
- **0** = none
- **1** = generic ("after dinner")
- **2** = specific ("birthday celebration", "post-bar nightcap")

### descriptive_depth — concrete reasoning vs. generic praise
- **0** = generic ("great", "amazing", "highly recommend")
- **1** = some specifics — at least one concrete detail or piece of reasoning
- **2** = highly concrete — sensory detail, comparisons, specific quantities, or narrative incident

## 8. The Three Retrieval Buckets

These are descriptions of *what kind of LLM query a review would surface for*, not judgments of the review's quality.

### service_attribute_matchable

Reviews that name a specific service or attribute. Surfaces for intent queries like "best salted caramel brownie in Charlotte" or "24-hour bakery near me" or "gluten-free pastries downtown."

### trust_quality_matchable

Reviews that describe practitioner or business qualities with concrete reasoning. No specific service named, but enough descriptive depth to surface for trust queries like "trustworthy dentist" or "honest mechanic" or "patient with anxious patients."

### low_retrievability

Reviews that don't contain enough specific language for any LLM query to anchor on. **Not a quality judgment.** These reviews still contribute to star ratings, review count, and social proof — they just don't carry semantic content for LLM retrieval.

## 9. Confidence Calibration

The labeler self-reports confidence on each review. Calibrated to per-review labelability, not rubric clarity.

- **high** — labels are unambiguous; review is clearly specific or clearly generic
- **medium** — small judgment calls were involved; one or two scores could be off by 1
- **low** — review is genuinely on the edge of the rubric

A 5-word generic review can be high-confidence (its genericness is unambiguous). A 5-word review with one weak signal is low-confidence (could go 0 or 1 on attributes).

The downstream report uses confidence to flag uncertain assignments for human review.

## 10. Framing Rules

The tool's output language must always be structural and descriptive. Never quality-laden.

**Do say:** "low-retrievability," "service/attribute-matchable," "the corpus enables matching for X," "the weakest dimension is occasion."

**Do not say:** "good reviews," "bad reviews," "your reviews are good enough," "improve your reviews."

Agencies will repeat the tool's language to clients. Every output string is potentially client-facing.

## 11. Honesty Constraints

- The gold set in `tests/fixtures/review_retrievability_gold_v3.json` is single-labeler synthetic. Agreement metrics computed against it are optimistically biased.
- Agreement numbers from the gold set are NOT to be presented as accuracy claims in user-facing output, marketing, or pitch material.
- The README and INPUT_SPEC document this. The caveats stay.
- When pitching: be honest that the gold set is Claude-produced and the model will work better when human-labeled gold replaces it.

## 12. Failure Modes the Tool Must Handle

- Empty corpus → fail clearly, do not run the pipeline
- Corpus too thin (<20 reviews) → run, but flag in the report that the diagnostic is provisional
- Malformed CSV/JSON → fail clearly with the row that broke
- LLM returns invalid JSON → retry once with corrective message; if second attempt fails, fall back to all-zeros for that review with confidence="low" and a note
- LLM API rate limit / timeout → exponential backoff, then fail clearly
- LLM API auth failure → fail immediately with a message about the API key
- Mixed-language reviews → score them anyway; the labeler handles non-English gracefully but the prompt is English

## 13. Versioning

The locked rubric and bucket rule are versioned. Current: **v2** (locked 2026-04-27).

Any change to dimensions, scale, definitions, or the bucket rule increments the version and invalidates the gold set's labels. A rubric change requires:
1. Re-labeling the gold set under the new rubric
2. Updating the prompts to match
3. Updating this SPEC document
4. Recording the change in BUILD_LOG.md

Do not change the rubric without doing all four.
