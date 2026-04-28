# Prompt Iteration Log

Running record of changes made to the labeler prompts and what they did to dev-split agreement. The labeler prompts are the heart of the product — this file is the experimental log of how they got tuned.

Format for each entry:

```
## YYYY-MM-DD — vN — short description

**Prompt file:** review_tool/prompts/{file}.md
**Change:** What was edited and why.
**Hypothesis:** What you expected this to fix.
**Dev-split bucket agreement:** before → after
**High-confidence disagreements:** before → after (count)
**Notes:** Anything weird in the disagreements list. New patterns surfaced.
```

Newest entries on top.

---

## 2026-04-28 — Session 3.2 — re-run dev-split; Milk Bar end-to-end observation

**Prompt file:** `review_tool/prompts/review_scorer.md` (no change — observation + baseline re-run only)
**Change:** None. Session 3.2 ran the dev-split evaluation again (same prompt, no edits) and ran the full pipeline on `tests/fixtures/milk_bar_sample.csv` (100 reviews, `--oneliner "Christina Tosi's Milk Bar"`).
**Hypothesis:** n/a — confirming baseline is stable; documenting observed labeler behavior on an unseen corpus.
**Dev-split bucket agreement:** 79.6% (v1) → **78.6% (77/98)** — 1 pp drop, within LLM sampling variance at temperature=0. Same 6 high-confidence disagreements as v1 baseline; no new patterns surfaced.
**High-confidence disagreements:** 6 → **6 (9.8%)** — unchanged.

**Outcome coverage observed: 96.0%** (96/100 reviews scored outcome ≥ 1)
**Expected for a consumption business (SPEC §7): ~12–25%**

**This is outcome over-scoring.** The labeler assigns outcome=1 on general satisfaction statements ("Crack pie was amazing", "didn't disappoint", "great experience") that have no problem/resolution arc. Examples:
- r_003: "I was so excited to come here and it didn't disappoint at all" → outcome=1 (should be 0)
- r_004: "Crack pie was amazing and everyone working there was very happy" → outcome=1 (should be 0)
- r_007: "unbeatable and the perfect way to end a great day in Vegas" → outcome=1 (should be 0)

**Impact on bucket counts: none.** `outcome` is not in the bucket rule. Bucket counts (96 SAM, 3 TQM, 1 LR) are determined by service, attributes, and descriptive_depth only.

**Impact on dimension coverage stats: significant.** The `DIMENSION COVERAGE` section of the report shows outcome at 96%, which is misleading — it implies the corpus is strong on this dimension when in fact the labeler is over-counting it.

**SAM at 96% is partially genuine for Milk Bar.** The brand has many specific trademarked products customers consistently name (crack pie, compost cookies, birthday cake, cereal milk soft serve). Most SAM assignments reviewed look defensible. The v1 baseline service over-scoring pattern (generic "donut"/"ice cream" → service=2) applies less here because Milk Bar's generics ("birthday cake", "soft serve") are actually specific branded items.

**Next prompt iteration priority:** Add explicit negative outcome examples for consumption businesses:
- "It was delicious" → outcome=0 (satisfaction, not a problem/resolution arc)
- "We loved it" → outcome=0
- "Didn't disappoint" → outcome=0
This should bring outcome coverage from ~96% down toward the expected ~16%.

---

## Anticipated iteration patterns

Likely things that will need tuning during the first few rounds. None of these are committed changes yet — they're hypotheses to test.

- **Labeler over-scores `outcome` in bakery reviews.** Despite explicit instruction in the prompt, the LLM may default to scoring `outcome=1` when a customer says "it was good." Watch for outcome coverage running >25% on Milk Bar — it should be ~15%.
- **Labeler conflates "specific service named" with "service mentioned."** "Pastries" might score 2 instead of 1. Watch for service coverage being unrealistically high.
- **Labeler gives high confidence on reviews it shouldn't.** A review with one weak signal ("nice atmosphere") should be low-confidence. If the labeler returns "high" too often, the calibration instruction needs sharpening.
- **Labeler scores operational vs. experiential attributes inconsistently.** "24/7" should weight higher than "friendly." Watch for the gap.
- **Labeler refuses to score relevance=false on off-topic reviews.** Reviews like "Just discovered Sugar Rush on Netflix..." should be flagged. If they're not, the relevance section of the prompt needs strengthening.

---

## Iteration log

---

### 2026-04-27 — v1 (initial) — baseline labeler

**Prompt file:** `review_tool/prompts/review_scorer.md`
**Change:** Initial production version, copied from the design phase. No edits made; this is the v1 baseline.
**Hypothesis:** n/a — establishing baseline.
**Dev-split bucket agreement:** — → **79.6% (78/98)**
**High-confidence disagreements:** — → **6 (9.8% of high-confidence reviews)**
**Notes:**

**Honesty caveat:** The gold set is single-labeler synthetic (produced by Claude). Agreement numbers measure consistency with the labeler's own training signal, not external accuracy. They are useful for tracking change across prompt iterations, not as quality claims. Do not cite the 79.6% figure as an accuracy number in any user-facing output, pitch material, or marketing copy.

Dev split: 98 reviews (48 `service_attribute_matchable`, 15 `trust_quality_matchable`, 35 `low_retrievability`).
Predictions saved to `outputs/labels_dev.json`.
Regression floor set at **0.75** in `tests/test_labeler_dev.py`.

**Per-dimension agreement:**

| dimension         | exact  | within-1 |
|-------------------|--------|----------|
| service           | 88.8%  | 95.9%    |
| attributes        | 65.3%  | 92.9%    |
| outcome           | 45.9%  | 99.0%    |
| occasion          | 79.6%  | 100.0%   |
| descriptive_depth | 80.6%  | 100.0%   |

**Disagreements by gold confidence:**

| conf   | total | bucket_disagree | rate  |
|--------|-------|-----------------|-------|
| high   |    61 |               6 |  9.8% |
| medium |    31 |              13 | 41.9% |
| low    |     6 |               1 | 16.7% |

**Relevance agreement: 100.0% (98/98)** — off-topic detection is working perfectly.

**Confusion matrix:**

|                            | SAM | TQM | LR |
|----------------------------|-----|-----|----|
| service_attribute_matchable |  45 |   1 |  2 |
| trust_quality_matchable     |   6 |   2 |  7 |
| low_retrievability          |   4 |   0 | 31 |

SAM = service_attribute_matchable, TQM = trust_quality_matchable, LR = low_retrievability.

**Patterns surfaced from 6 high-confidence bucket disagreements:**

1. **Labeler over-scores `service` for generic category mentions.** "Every donut" (r_096) scored service=2; gold says 0. "Best ice cream ever" (r_051) scored service=2; gold says 0. The labeler treats "donut" and "ice cream" as specific named items when they are generic product categories.

2. **Labeler under-scores `attributes` for operational specifics.** "Lines are long" (r_019) is an operational attribute and should reach attributes=2; labeler scored 1. "Mona Lisa everywhere" (r_013) is a concrete visual attribute that should trigger attributes=2; labeler scored 1.

3. **Labeler under-scores `descriptive_depth` on medium-length reviews.** "The whole experience felt smooth and well-organized" (u_021) has structural specificity that earns depth=1; labeler scored 0.

4. **Specific named items ("Chi Tea latte") are misclassified as generic.** r_034: "Chi Tea latte was amazing!!!" — labeler gives service=1 (generic) vs gold service=2 (named item). The drink name is clearly a specific named item.

**Biggest weakness: `trust_quality_matchable` bucket.** Only 2 of 15 TQM reviews land correctly (13.3%). Most either over-score into SAM or under-score into LR. The labeler struggles to distinguish depth=1 from depth=0 in reviews without explicit named items.

**`outcome` dimension fires too often.** 45.9% exact agreement but 99% within-1 — almost all errors are 0→1 over-scores. The labeler infers an implied outcome ("enjoyed it") where gold assigns 0. This is structurally expected for consumption businesses (per SPEC §7), but the labeler isn't applying the restraint consistently.

**Next iteration ideas (not yet implemented):**
- Add explicit examples of "donut" / "ice cream" scoring as service=1 (not 2) to few-shot examples
- Add an example distinguishing "Lines are long on weekends" → attributes=2 vs "friendly staff" → attributes=1
- Add a negative example for outcome: "It was delicious" → outcome=0 (no problem/resolution arc)
- Add an explicit example of a TQM review that has depth=1 but no named service

---

## Things to never include in the labeler prompt

These were tested in earlier iterations and don't help. Don't re-add them.

*(populated as anti-patterns are discovered)*
