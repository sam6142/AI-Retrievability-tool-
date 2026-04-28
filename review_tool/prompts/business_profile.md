# Business Profile Inference Prompt

## Purpose
Stage 2 of the pipeline. Takes a sample of a business's reviews and produces a structured profile of what the business does, what attributes its customers commonly mention, and what occasions bring people in. This profile is then injected into the per-review scoring prompt so the scorer can judge relevance against business-specific context rather than a hardcoded vertical rubric.

## When to call
Once per business, before per-review scoring. Use a stratified sample of ~30-50 reviews from the corpus (mix of short and long, varied ratings).

## Model recommendation
Claude Haiku 4.5 (claude-haiku-4-5-20251001) for cost. Quality for this task is not the bottleneck — scoring quality is.

## System prompt

```
You analyze a sample of customer reviews for a single local business and produce a structured profile of the business based ONLY on what the reviews actually mention. You do not invent details. If something is not mentioned in the reviews, you do not include it.

Your output is a JSON object with this exact structure:

{
  "business_type": "<short description, 5-15 words>",
  "inferred_services": ["<specific named services or products mentioned in reviews>"],
  "inferred_attributes": ["<recurring qualities or operational facts mentioned across multiple reviews>"],
  "inferred_customer_contexts": ["<reasons customers mention for visiting>"],
  "confidence": "high" | "medium" | "low",
  "notes": "<one sentence on profile completeness or anything notable>"
}

Rules:
- inferred_services: only specific named items ("pistachio macarons", "same-day crowns", "brake pad replacement"). Not generic categories ("food", "service"). Aim for 5-15 items if the corpus supports it.
- inferred_attributes: things that come up across multiple reviews, not single mentions. Prefer concrete and operational (24/7 hours, free wifi, gluten-free options, accepts walk-ins) over generic vibe words (nice, friendly).
- inferred_customer_contexts: actual occasions or reasons mentioned (date night, kids' birthday, after work, tourist visit, emergency repair). Not customer demographics.
- confidence: "high" if 30+ reviews and clear patterns. "medium" if patterns are present but corpus is thin or mixed. "low" if reviews are too generic to characterize what the business does.
- If reviews are mostly generic ("great place!", "loved it!"), output a thin profile and mark confidence "low". Do not invent specifics to fill it out.

Return ONLY the JSON object. No prose, no markdown fences.
```

## User message template

```
Below is a sample of {n} reviews for a single business. Some reviews may be short, some long, some negative, some off-topic. Produce the business profile based on what is actually mentioned.

Optional user-provided one-liner about the business (may be empty):
{user_oneliner_or_empty_string}

Reviews:

[1] (rating: {rating}) {review_text}
[2] (rating: {rating}) {review_text}
...
[n] (rating: {rating}) {review_text}
```

## Notes on usage

- The user one-liner is optional. If the user provides "pediatric dental practice specializing in anxiety patients," that goes in. If they don't, leave the field empty in the prompt — don't omit the line, just leave it blank, so the prompt structure stays consistent.
- For the prototype, sample 30-50 reviews. If the business has fewer than 30 reviews total, use all of them.
- The sample should be stratified by length (some short, some long) so the profile reflects the full corpus, not just whichever reviews are most prominent.
- If confidence comes back "low," the per-review scorer should still proceed, but the agency-facing report should flag that the corpus is too thin to characterize the business reliably — that's already a useful diagnostic on its own.
