# Input Specification — Review Retrievability Tool (Prototype)

## Required input

A file of reviews for one business, in either CSV or JSON format.

### CSV format

```csv
review_text,rating,date
"Got a same-day crown...",5,2024-03-15
"Great place!",4,2024-04-02
```

| Column | Required | Type | Notes |
|---|---|---|---|
| `review_text` | yes | string | The review content. Must be non-empty. |
| `rating` | optional | integer 1-5 | Not used for scoring; surfaced in report. |
| `date` | optional | string | Free-form. Used for filtering/sorting only. |
| `review_id` | optional | string | If absent, tool generates `r_001`, `r_002`, etc. |

### JSON format

```json
[
  {
    "review_id": "r_001",
    "review_text": "Got a same-day crown...",
    "rating": 5,
    "date": "2024-03-15"
  },
  ...
]
```

Same field requirements as CSV.

## Optional input

A one-line free-text description of the business. ~5–30 words.

Examples:
- *"Pediatric dental practice specializing in anxiety patients"*
- *"Italian bakery in Cleveland's Little Italy, family-run since 1903"*
- *"Christina Tosi's Milk Bar — known for Cereal Milk soft-serve and Crack Pie"*

This goes into the Stage 2 business-profile inference prompt. Useful when the business has thin reviews or specialty positioning that doesn't surface in the corpus.

If not provided, the tool runs without it. The Stage 2 prompt has an empty-string placeholder for this case.

## CLI signature

```bash
python -m review_tool.analyze \
    --reviews path/to/reviews.csv \
    --oneliner "Christina Tosi's Milk Bar" \
    --output path/to/report_dir/
```

Output directory contains:
- `report.json` — full structured output (per-review labels + corpus rollup + business profile)
- `report.txt` — human-readable templated summary

## What the tool does NOT take

Worth being explicit:

- **No business name lookup or Google Maps URL.** No external API calls.
- **No Google Business Profile auth.** Deferred to future scope.
- **No vertical/category selection.** Inferred from corpus.
- **No pre-classified reviews.** Tool labels everything from raw text.
- **No rubric tuning by user.** The five dimensions and bucket rule are locked.

## Corpus size guidance

| Reviews | Behavior |
|---|---|
| <20 | Tool will run but flag corpus-too-thin in the report. Business profile confidence likely "low". |
| 20–500 | Normal operating range. |
| 500+ | Tool runs but flags that this is a slow run (1 LLM call per review). Future scope: batching. |
| 5000+ | Tool will warn and require an explicit `--allow-large` flag before proceeding. |

For the prototype, anything from 30–500 reviews is the sweet spot for testing.
