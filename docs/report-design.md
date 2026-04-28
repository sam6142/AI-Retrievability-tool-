# Report Design — Output Format Specification

Defines exactly what `report.json` and `report.txt` look like. Locked because agencies will quote the language to clients — wording matters and must stay neutral.

---

## report.json

Schema in `review_tool/schemas/corpus_report.json`. Top-level structure:

```json
{
  "metadata": {
    "tool_version": "0.1.0",
    "rubric_version": "v2",
    "generated_at": "2026-04-27T14:32:11Z",
    "input_file": "milk_bar_sample.csv",
    "input_review_count_raw": 100,
    "input_review_count_after_cleaning": 98,
    "user_oneliner": "Christina Tosi's Milk Bar at the Cosmopolitan, Las Vegas"
  },
  "business_profile": {
    "business_type": "...",
    "inferred_services": ["...", "..."],
    "inferred_attributes": ["...", "..."],
    "inferred_customer_contexts": ["...", "..."],
    "confidence": "high",
    "notes": "..."
  },
  "corpus_stats": {
    "total_reviews": 98,
    "by_bucket": {
      "service_attribute_matchable": 71,
      "trust_quality_matchable": 14,
      "low_retrievability": 13
    },
    "ai_visibility_pct": 86.7,
    "dimension_coverage_pct": {
      "service": 78.6,
      "attributes": 71.4,
      "outcome": 12.2,
      "occasion": 38.8,
      "descriptive_depth": 67.3
    },
    "weakest_dimension": "outcome",
    "confidence_distribution": {
      "high": 65,
      "medium": 23,
      "low": 10
    }
  },
  "examples_per_bucket": {
    "service_attribute_matchable": ["mb_007", "mb_022", "mb_058"],
    "trust_quality_matchable": ["mb_011", "mb_034", "mb_077"],
    "low_retrievability": ["mb_005", "mb_041", "mb_089"]
  },
  "scored_reviews": [
    {
      "review_id": "mb_001",
      "text": "...",
      "rating": 5,
      "date": "2024-03-15",
      "labels": {"service": 2, "attributes": 1, "outcome": 0, "occasion": 0, "descriptive_depth": 1},
      "relevance": true,
      "confidence": "high",
      "bucket": "service_attribute_matchable",
      "rationale": {
        "service": "Cereal Milk soft-serve named",
        "attributes": "Cosmo location mentioned",
        "outcome": "No outcome described",
        "occasion": "No occasion",
        "descriptive_depth": "Some sensory detail"
      }
    }
  ]
}
```

The runtime output uses `bucket` (no qualifier — it's the assigned bucket for this review). The gold set fixture uses `expected_bucket` (because the gold has a target bucket the labeler is being evaluated against). They refer to the same concept; the field name differs by context.

## report.html

A self-contained HTML file written alongside `report.json` and `report.txt`. Opens offline in any modern browser. No external dependencies, no CDN links, no JavaScript.

### Layout (top to bottom)

1. **Header** — project name, business type, review count, generation date.
2. **Headline** — large `ai_visibility_pct` numeral (visual focal point) + bucket counts. Thin-corpus note if `total_reviews < 20`.
3. **Bucket Distribution** — single horizontal stacked-bar SVG (yellow = SAM, light-gray = TQM, dark-gray = LR). Segment labels appear inline when the segment is wide enough; a legend is always shown below.
4. **Dimension Coverage** — five horizontal bar SVGs; yellow fill on dark-gray track. Weakest dimension label is highlighted yellow with a `◄` marker.
5. **Business Profile** — inferred services, attributes, customer contexts as bullet lists. Profile confidence shown. Low-confidence note if `confidence == "low"`.
6. **Examples** — up to 3 cards per bucket. Each card shows: review ID, confidence, review text (truncated at 120 chars), dimension score chips (active chips highlighted yellow), per-dimension rationale.
7. **Labeling Confidence** — high/medium/low counts and percentages.
8. **Footer** — caveats + fixed line: "Retrievability is a structural property of review content — not a judgment of review quality."

### Style

- Background: `#000000`
- Accent / headings / chart fills: `#FFE600`
- Body text: `#EEEEEE`
- Borders and dividers: `#333333`
- Three colors only; no gradients, no shadows, no decorative elements.
- System font stack; no web fonts.

### Wording

Same rules as `report.txt`. The fixed footer line replaces free-form CAVEATS prose.

### Implementation

`render_html_report(report: dict) -> str` in `review_tool/report.py`. `write_report()` calls it and writes `report.html`.

---

## report.txt

A templated, human-readable summary. The agency will read this in their terminal or paste it into a deck or email to a client. Wording is fixed; only the numbers vary.

### Template

```
═══════════════════════════════════════════════════════════════
REVIEW RETRIEVABILITY REPORT
═══════════════════════════════════════════════════════════════

Business: {business_type}
Reviews analyzed: {total_reviews}
Generated: {date}

───────────────────────────────────────────────────────────────
HEADLINE
───────────────────────────────────────────────────────────────

Of {total_reviews} reviews:
  • {bucket_1_count} are service/attribute-matchable
  • {bucket_2_count} are trust/quality-matchable
  • {bucket_3_count} are low-retrievability

Combined LLM-retrievability: {ai_visibility_pct}%

The corpus is currently positioned to surface this business for
specific-service and trust-quality LLM queries on roughly
{rounded_pct}% of its reviews. The remaining {bucket_3_count} reviews
do not carry sufficient semantic content for LLM retrieval, though
they continue to function for star ratings and social proof.

───────────────────────────────────────────────────────────────
DIMENSION COVERAGE
───────────────────────────────────────────────────────────────

Percent of reviews mentioning each dimension at least generically:

  Service / product named ........... {service_pct}%
  Attributes (qualities) ............ {attributes_pct}%
  Outcome described ................. {outcome_pct}%
  Occasion / context indicated ...... {occasion_pct}%
  Descriptive depth ................. {depth_pct}%

Weakest dimension: {weakest_dimension}

───────────────────────────────────────────────────────────────
BUSINESS PROFILE (inferred from reviews)
───────────────────────────────────────────────────────────────

Type: {business_type}

Services mentioned across the corpus:
  {bullet_list_of_services}

Attributes commonly noted:
  {bullet_list_of_attributes}

Customer contexts seen:
  {bullet_list_of_contexts}

Profile inference confidence: {profile_confidence}
{optional_thin_corpus_warning}

───────────────────────────────────────────────────────────────
EXAMPLES
───────────────────────────────────────────────────────────────

Service/attribute-matchable (sample):
  [{example_1_id}] "{example_1_text_truncated_120_chars}"
  [{example_2_id}] "{example_2_text_truncated_120_chars}"
  [{example_3_id}] "{example_3_text_truncated_120_chars}"

Trust/quality-matchable (sample):
  [{example_4_id}] "..."
  [{example_5_id}] "..."

Low-retrievability (sample):
  [{example_6_id}] "..."
  [{example_7_id}] "..."

───────────────────────────────────────────────────────────────
LABELING CONFIDENCE
───────────────────────────────────────────────────────────────

The labeler self-reported confidence on each review:
  High confidence:   {high_count} ({high_pct}%)
  Medium confidence: {medium_count} ({medium_pct}%)
  Low confidence:    {low_count} ({low_pct}%)

Low-confidence assignments are reviews where the rubric is
genuinely ambiguous. They are flagged in the JSON output for
optional human review.

───────────────────────────────────────────────────────────────
CAVEATS
───────────────────────────────────────────────────────────────

This is a prototype diagnostic. Findings are based on the
provided review corpus alone and do not account for review
recency, geographic relevance, or query-specific retrieval
behavior. The retrieval bucket assignments reflect what each
review's content enables, not whether the review is "good."

═══════════════════════════════════════════════════════════════
```

### Wording rules

These are not negotiable in the templated output. They protect the framing.

- **Always** "low-retrievability," never "low-quality" or "weak" or "bad"
- **Always** "the corpus is positioned to..." or "the corpus enables..." — descriptive of capability
- **Never** "good enough," "should improve," or any prescriptive language
- **Never** assign blame to the reviews ("your customers aren't writing well")
- Numbers are reported to one decimal place
- Buckets use their full name in headlines, abbreviated names ("bucket 1") never appear in user-facing output

### Conditional sections

If `business_profile.confidence == "low"`, append after the BUSINESS PROFILE section:

```
NOTE: The review corpus is too thin or generic to characterize
this business reliably. The profile above represents a
best-effort inference; the diagnostic that follows should be
read as provisional.
```

If `total_reviews < 20`, prepend after HEADLINE:

```
NOTE: This corpus contains fewer than 20 reviews. Findings are
provisional. Larger corpora produce more reliable retrievability
diagnostics.
```

If `dimension_coverage_pct["outcome"] < 20`, do NOT flag this — for consumption businesses (bakery, café), low outcome coverage is structural and expected. The "weakest dimension" line still names it, which is enough.

### Numeric rounding

- Percentages: 1 decimal place
- AI-visibility: 1 decimal place
- Counts: integers, no formatting

### Empty / edge cases

- If `bucket_2_count == 0`: still print the line, "0 are trust/quality-matchable." Do not omit.
- If `ai_visibility_pct == 0`: print "0.0%" — do not panic-tone.
- If a dimension coverage is 0%: print "0.0%" plainly. The output is descriptive, not alarmist.

### Examples

If a corpus has only 1–2 reviews per bucket, show what's available — do not pad with "see JSON for more." Truncate text at 120 characters with `...` ellipsis if longer.
