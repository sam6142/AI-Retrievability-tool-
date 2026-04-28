"""Stage 6: Report generation — JSON output and deterministic text summary.

build_report()       → assemble + validate the full CorpusReport dict
render_text_report() → produce report.txt from the dict (no LLM calls)
write_report()       → write report.json and report.txt to disk
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import jsonschema

from review_tool.aggregate import CorpusStats, ScoredReview
from review_tool.classify import BUCKETS
from review_tool.ingest import Review

logger = logging.getLogger(__name__)

_SCHEMAS_DIR = Path(__file__).parent / "schemas"
_HEAVY = "═" * 63
_LIGHT = "─" * 63


def _report_schema() -> dict:
    return json.loads((_SCHEMAS_DIR / "corpus_report.json").read_text(encoding="utf-8"))


def _pick_examples(
    scored_reviews: list[ScoredReview], max_per_bucket: int = 3
) -> dict[str, list[str]]:
    """Return up to max_per_bucket review_ids per bucket in corpus order."""
    buckets: dict[str, list[str]] = {b: [] for b in BUCKETS}
    for sr in scored_reviews:
        b = sr["bucket"]
        if b in buckets and len(buckets[b]) < max_per_bucket:
            buckets[b].append(sr["review_id"])
    return buckets


def build_report(
    reviews: list[Review],
    scored_reviews: list[ScoredReview],
    business_profile: dict,
    corpus_stats: dict,
    metadata: dict,
) -> dict:
    """Assemble the full CorpusReport and validate it against corpus_report.json.

    Raises jsonschema.ValidationError if the assembled report does not match the schema.
    """
    examples = _pick_examples(scored_reviews)
    report: dict[str, Any] = {
        "metadata": metadata,
        "business_profile": business_profile,
        "corpus_stats": corpus_stats,
        "examples_per_bucket": examples,
        "scored_reviews": list(scored_reviews),
    }
    jsonschema.validate(report, _report_schema())
    logger.info("Report assembled and validated against corpus_report.json.")
    return report


# ---------------------------------------------------------------------------
# Text rendering helpers
# ---------------------------------------------------------------------------

def _truncate(text: str, max_len: int = 120) -> str:
    return text if len(text) <= max_len else text[:max_len] + "..."


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "  (none identified)"
    return "\n".join(f"  • {item}" for item in items)


def _section(title: str) -> str:
    """Return a section header block element.

    When appended to the lines list and the list is joined with '\\n', this
    produces one blank line before the dividers and one blank line after:

        <blank line>
        ─────────────────────────────────────────────────────────────────
        TITLE
        ─────────────────────────────────────────────────────────────────
        <blank line>

    The leading '\\n' combines with the join separator to give the blank line
    before.  The trailing '\\n' combines with the join separator to give the
    blank line after.
    """
    return f"\n{_LIGHT}\n{title}\n{_LIGHT}\n"


def render_text_report(report: dict) -> str:
    """Build the human-readable report.txt string from a validated report dict.

    Uses the fixed template from docs/report-design.md.  No LLM calls.
    Wording rules and conditional sections are applied as specified.
    """
    meta: dict = report["metadata"]
    bp: dict = report["business_profile"]
    cs: dict = report["corpus_stats"]
    epb: dict = report["examples_per_bucket"]
    scored: list[dict] = report["scored_reviews"]

    total: int = cs["total_reviews"]
    by_b: dict = cs["by_bucket"]
    b1: int = by_b["service_attribute_matchable"]
    b2: int = by_b["trust_quality_matchable"]
    b3: int = by_b["low_retrievability"]
    ai_pct: float = cs["ai_visibility_pct"]
    dim: dict = cs["dimension_coverage_pct"]
    weakest: str = cs["weakest_dimension"]
    conf: dict = cs["confidence_distribution"]

    date_str = (meta.get("generated_at") or "")[:10]
    lookup: dict[str, dict] = {sr["review_id"]: sr for sr in scored}

    lines: list[str] = []

    # ── Report header ────────────────────────────────────────────────────────
    lines += [
        _HEAVY,
        "REVIEW RETRIEVABILITY REPORT",
        _HEAVY,
        "",
        f"Business: {bp['business_type']}",
        f"Reviews analyzed: {total}",
        f"Generated: {date_str}",
    ]

    # ── HEADLINE ─────────────────────────────────────────────────────────────
    lines.append(_section("HEADLINE"))

    if total < 20:
        lines += [
            (
                "NOTE: This corpus contains fewer than 20 reviews. Findings are\n"
                "provisional. Larger corpora produce more reliable retrievability\n"
                "diagnostics."
            ),
            "",
        ]

    lines += [
        f"Of {total} reviews:",
        f"  • {b1} are service/attribute-matchable",
        f"  • {b2} are trust/quality-matchable",
        f"  • {b3} are low-retrievability",
        "",
        f"Combined LLM-retrievability: {ai_pct:.1f}%",
        "",
        (
            f"The corpus is currently positioned to surface this business for\n"
            f"specific-service and trust-quality LLM queries on roughly\n"
            f"{ai_pct:.1f}% of its reviews. The remaining {b3} reviews\n"
            f"do not carry sufficient semantic content for LLM retrieval, though\n"
            f"they continue to function for star ratings and social proof."
        ),
    ]

    # ── DIMENSION COVERAGE ───────────────────────────────────────────────────
    lines.append(_section("DIMENSION COVERAGE"))
    lines += [
        "Percent of reviews mentioning each dimension at least generically:",
        "",
        f"  Service / product named ........... {dim['service']:.1f}%",
        f"  Attributes (qualities) ............ {dim['attributes']:.1f}%",
        f"  Outcome described ................. {dim['outcome']:.1f}%",
        f"  Occasion / context indicated ...... {dim['occasion']:.1f}%",
        f"  Descriptive depth ................. {dim['descriptive_depth']:.1f}%",
        "",
        f"Weakest dimension: {weakest}",
    ]

    # ── BUSINESS PROFILE ─────────────────────────────────────────────────────
    lines.append(_section("BUSINESS PROFILE (inferred from reviews)"))
    lines += [
        f"Type: {bp['business_type']}",
        "",
        "Services mentioned across the corpus:",
        _bullet_list(bp.get("inferred_services", [])),
        "",
        "Attributes commonly noted:",
        _bullet_list(bp.get("inferred_attributes", [])),
        "",
        "Customer contexts seen:",
        _bullet_list(bp.get("inferred_customer_contexts", [])),
        "",
        f"Profile inference confidence: {bp['confidence']}",
    ]

    if bp.get("confidence") == "low":
        lines += [
            "",
            (
                "NOTE: The review corpus is too thin or generic to characterize\n"
                "this business reliably. The profile above represents a\n"
                "best-effort inference; the diagnostic that follows should be\n"
                "read as provisional."
            ),
        ]

    # ── EXAMPLES ─────────────────────────────────────────────────────────────
    lines.append(_section("EXAMPLES"))

    bucket_labels = [
        ("service_attribute_matchable", "Service/attribute-matchable (sample):"),
        ("trust_quality_matchable", "Trust/quality-matchable (sample):"),
        ("low_retrievability", "Low-retrievability (sample):"),
    ]
    for idx, (bk, label) in enumerate(bucket_labels):
        lines.append(label)
        ids: list[str] = epb.get(bk, [])
        if ids:
            for rid in ids:
                sr = lookup.get(rid)
                text = sr["text"] if sr else ""
                lines.append(f'  [{rid}] "{_truncate(text)}"')
        else:
            lines.append("  (no reviews in this bucket)")
        if idx < len(bucket_labels) - 1:
            lines.append("")

    # ── LABELING CONFIDENCE ──────────────────────────────────────────────────
    lines.append(_section("LABELING CONFIDENCE"))
    h, m, lo = conf["high"], conf["medium"], conf["low"]
    safe_total = total if total > 0 else 1
    lines += [
        "The labeler self-reported confidence on each review:",
        f"  {'High confidence:':<19} {h} ({h / safe_total * 100:.1f}%)",
        f"  {'Medium confidence:':<19} {m} ({m / safe_total * 100:.1f}%)",
        f"  {'Low confidence:':<19} {lo} ({lo / safe_total * 100:.1f}%)",
        "",
        (
            "Low-confidence assignments are reviews where the rubric is\n"
            "genuinely ambiguous. They are flagged in the JSON output for\n"
            "optional human review."
        ),
    ]

    # ── CAVEATS ──────────────────────────────────────────────────────────────
    lines.append(_section("CAVEATS"))
    lines += [
        (
            "This is a prototype diagnostic. Findings are based on the\n"
            "provided review corpus alone and do not account for review\n"
            "recency, geographic relevance, or query-specific retrieval\n"
            "behavior. The retrieval bucket assignments reflect what each\n"
            'review\'s content enables, not whether the review is "good."'
        ),
        "",
        _HEAVY,
    ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# File output
# ---------------------------------------------------------------------------

def write_report(report: dict, output_dir: Path) -> None:
    """Write report.json and report.txt to output_dir, creating it if needed."""
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "report.json"
    txt_path = output_dir / "report.txt"

    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Wrote %s", json_path)

    txt_path.write_text(render_text_report(report), encoding="utf-8")
    logger.info("Wrote %s", txt_path)
