"""Stage 2: Business profile inference from a stratified review sample."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import TypedDict

from review_tool import llm_client
from review_tool.ingest import Review

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_SCHEMAS_DIR = Path(__file__).parent / "schemas"

_SAMPLE_SIZE = 30
_THIN_CORPUS_HARD = 10   # below this: severe warning
_THIN_CORPUS_SOFT = 20   # below this: force confidence = "low"

_FENCE_RE = re.compile(r"```[a-z]*\n(.*?)```", re.DOTALL)


# ---------------------------------------------------------------------------
# Output type
# ---------------------------------------------------------------------------

class BusinessProfile(TypedDict):
    business_type: str
    inferred_services: list[str]
    inferred_attributes: list[str]
    inferred_customer_contexts: list[str]
    confidence: str
    notes: str


# ---------------------------------------------------------------------------
# Prompt and schema loading
# ---------------------------------------------------------------------------

def _load_prompt_blocks() -> tuple[str, str]:
    """Return (system_prompt, user_message_template) from business_profile.md."""
    text = (_PROMPTS_DIR / "business_profile.md").read_text(encoding="utf-8")
    blocks = _FENCE_RE.findall(text)
    if len(blocks) < 2:
        raise RuntimeError(
            "business_profile.md must contain at least 2 fenced code blocks "
            "(system prompt and user message template)."
        )
    return blocks[0].strip(), blocks[1].strip()


def _load_schema() -> dict:
    return json.loads((_SCHEMAS_DIR / "business_profile.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Sample stratification
# ---------------------------------------------------------------------------

def _stratify_sample(reviews: list[Review], n: int = _SAMPLE_SIZE) -> list[Review]:
    """Return up to n reviews spread evenly across the word-count distribution.

    Sorting by word count and sampling at regular intervals gives a mix of
    short and long reviews rather than biasing toward whichever happen to appear
    first in the corpus.
    """
    if len(reviews) <= n:
        return list(reviews)
    sorted_r = sorted(reviews, key=lambda r: len(r["text"].split()))
    step = len(sorted_r) / n
    return [sorted_r[int(i * step)] for i in range(n)]


# ---------------------------------------------------------------------------
# User message construction
# ---------------------------------------------------------------------------

def _build_user_message(
    sample: list[Review],
    template: str,
    oneliner: str | None,
) -> str:
    """Substitute the header fields and build the numbered review list."""
    # Split at "Reviews:" — everything before is the header, which we substitute;
    # everything after is just the illustrative [1]...[n] format we discard.
    header_part, _, _ = template.partition("Reviews:")

    header_part = header_part.replace("{n}", str(len(sample)))
    header_part = header_part.replace(
        "{user_oneliner_or_empty_string}", oneliner or ""
    )

    review_lines: list[str] = []
    for i, r in enumerate(sample, start=1):
        rating_str = str(r["rating"]) if r["rating"] is not None else "N/A"
        review_lines.append(f"[{i}] (rating: {rating_str}) {r['text']}")

    return header_part + "Reviews:\n\n" + "\n".join(review_lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def infer_profile(
    reviews: list[Review],
    oneliner: str | None = None,
    sample_size: int = _SAMPLE_SIZE,
) -> BusinessProfile:
    """Infer a structured business profile from the review corpus.

    Calls Haiku once with a stratified sample of up to 30 reviews.
    Forces confidence to 'low' if the corpus has fewer than 20 reviews
    (per edge-cases-tracker.md — too thin to characterise reliably).

    Args:
        reviews: Cleaned review list from ingest.ingest().
        oneliner: Optional user-supplied one-line business description.

    Returns:
        Validated BusinessProfile dict.
    """
    n = len(reviews)

    if n < _THIN_CORPUS_HARD:
        logger.warning(
            "Corpus has only %d reviews — profile inference is highly unreliable "
            "with so few examples.",
            n,
        )
    elif n < _THIN_CORPUS_SOFT:
        logger.warning(
            "Corpus has %d reviews (recommended minimum: %d). "
            "Profile confidence will be overridden to 'low'.",
            n,
            _THIN_CORPUS_SOFT,
        )

    system_prompt, user_template = _load_prompt_blocks()
    schema = _load_schema()
    sample = _stratify_sample(reviews, n=sample_size)

    logger.info(
        "Inferring business profile from %d reviews (sample size: %d).",
        n,
        len(sample),
    )

    user_message = _build_user_message(sample, user_template, oneliner)

    result: BusinessProfile = llm_client.call_with_validation(  # type: ignore[assignment]
        system_prompt=system_prompt,
        user_message=user_message,
        schema=schema,
    )

    # Deterministic override: thin corpora cannot be reliably characterised
    if n < _THIN_CORPUS_SOFT:
        result["confidence"] = "low"

    if result.get("confidence") == "low":
        logger.warning(
            "Business profile confidence is 'low' — corpus may be too thin or too "
            "generic to characterise the business reliably. The report should flag this."
        )

    logger.info(
        "Profile inferred: business_type=%r, confidence=%r, "
        "%d services, %d attributes, %d contexts.",
        result.get("business_type"),
        result.get("confidence"),
        len(result.get("inferred_services", [])),
        len(result.get("inferred_attributes", [])),
        len(result.get("inferred_customer_contexts", [])),
    )

    return result
