"""Tests for review_tool/report.py — Stage 6 report generation.

All tests are deterministic; no LLM calls.
"""
from __future__ import annotations

import pytest
import jsonschema

from review_tool.report import build_report, render_html_report, render_text_report

# ── Test data helpers ────────────────────────────────────────────────────────

_DIMS = ("service", "attributes", "outcome", "occasion", "descriptive_depth")
_ZERO_LABELS = {d: 0 for d in _DIMS}
_ZERO_RATIONALE = {d: "" for d in _DIMS}


def _review(rid: str, text: str = "placeholder") -> dict:
    return {"review_id": rid, "text": text, "rating": 4, "date": "2024-01-01"}


def _scored(
    rid: str,
    bucket: str = "low_retrievability",
    confidence: str = "medium",
    text: str = "placeholder",
) -> dict:
    return {
        "review_id": rid,
        "text": text,
        "rating": 4,
        "date": "2024-01-01",
        "labels": _ZERO_LABELS.copy(),
        "relevance": True,
        "confidence": confidence,
        "bucket": bucket,
        "rationale": _ZERO_RATIONALE.copy(),
    }


def _metadata(raw: int = 3, clean: int = 3) -> dict:
    return {
        "tool_version": "0.1.0",
        "rubric_version": "v2",
        "generated_at": "2026-04-27T12:00:00Z",
        "input_file": "test.csv",
        "input_review_count_raw": raw,
        "input_review_count_after_cleaning": clean,
    }


def _profile(confidence: str = "high") -> dict:
    return {
        "business_type": "bakery",
        "inferred_services": ["croissants"],
        "inferred_attributes": ["cozy"],
        "inferred_customer_contexts": ["morning visit"],
        "confidence": confidence,
        "notes": "",
    }


def _stats(
    total: int = 3,
    b1: int = 1,
    b2: int = 1,
    b3: int = 1,
    weakest: str = "outcome",
    conf_dist: dict | None = None,
) -> dict:
    ai_pct = round((b1 + b2) / max(total, 1) * 100, 1)
    return {
        "total_reviews": total,
        "by_bucket": {
            "service_attribute_matchable": b1,
            "trust_quality_matchable": b2,
            "low_retrievability": b3,
        },
        "ai_visibility_pct": ai_pct,
        "dimension_coverage_pct": {d: 0.0 for d in _DIMS},
        "weakest_dimension": weakest,
        "confidence_distribution": conf_dist or {"high": 0, "medium": total, "low": 0},
    }


def _build(
    *,
    scored_reviews: list[dict] | None = None,
    profile: dict | None = None,
    corpus_stats: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    """Assemble a minimal valid CorpusReport; caller can override any field."""
    scored = scored_reviews or [
        _scored("r_001", "service_attribute_matchable"),
        _scored("r_002", "trust_quality_matchable"),
        _scored("r_003", "low_retrievability"),
    ]
    n = len(scored)
    b1 = sum(1 for s in scored if s["bucket"] == "service_attribute_matchable")
    b2 = sum(1 for s in scored if s["bucket"] == "trust_quality_matchable")
    b3 = sum(1 for s in scored if s["bucket"] == "low_retrievability")
    return build_report(
        reviews=[_review(s["review_id"], s["text"]) for s in scored],
        scored_reviews=scored,
        business_profile=profile or _profile(),
        corpus_stats=corpus_stats or _stats(n, b1, b2, b3),
        metadata=metadata or _metadata(n, n),
    )


# ── build_report: structure and schema ──────────────────────────────────────

@pytest.mark.fast
def test_build_report_top_level_keys():
    """build_report returns all required top-level keys."""
    report = _build()
    assert set(report.keys()) == {
        "metadata", "business_profile", "corpus_stats",
        "examples_per_bucket", "scored_reviews",
    }


@pytest.mark.fast
def test_build_report_examples_per_bucket_populated():
    """examples_per_bucket contains one id per bucket from scored_reviews."""
    report = _build()
    epb = report["examples_per_bucket"]
    assert "r_001" in epb["service_attribute_matchable"]
    assert "r_002" in epb["trust_quality_matchable"]
    assert "r_003" in epb["low_retrievability"]


@pytest.mark.fast
def test_build_report_all_low_retrievability():
    """build_report is valid when all reviews land in low_retrievability."""
    scored = [_scored(f"r_{i:03}", "low_retrievability") for i in range(1, 4)]
    report = _build(scored_reviews=scored, corpus_stats=_stats(3, 0, 0, 3))
    assert report["corpus_stats"]["by_bucket"]["low_retrievability"] == 3
    assert report["examples_per_bucket"]["service_attribute_matchable"] == []
    assert report["examples_per_bucket"]["trust_quality_matchable"] == []


@pytest.mark.fast
def test_build_report_scored_reviews_preserved():
    """All scored_reviews appear in the report output."""
    report = _build()
    assert len(report["scored_reviews"]) == 3


@pytest.mark.fast
def test_build_report_schema_mismatch_raises():
    """build_report raises jsonschema.ValidationError when business_profile is incomplete."""
    bad_profile = {"business_type": "bakery"}  # missing required fields
    with pytest.raises(jsonschema.ValidationError):
        _build(profile=bad_profile)


@pytest.mark.fast
def test_build_report_invalid_bucket_in_stats_raises():
    """build_report raises ValidationError when by_bucket is missing a key."""
    bad_stats = _stats()
    del bad_stats["by_bucket"]["low_retrievability"]
    with pytest.raises(jsonschema.ValidationError):
        _build(corpus_stats=bad_stats)


# ── render_text_report: zero-bucket lines always present ────────────────────

@pytest.mark.fast
def test_render_zero_trust_bucket_line_present():
    """'0 are trust/quality-matchable' is rendered, not omitted, when b2 = 0."""
    scored = [
        _scored("r_001", "service_attribute_matchable"),
        _scored("r_002", "service_attribute_matchable"),
        _scored("r_003", "low_retrievability"),
    ]
    report = _build(scored_reviews=scored, corpus_stats=_stats(3, 2, 0, 1))
    text = render_text_report(report)
    assert "• 0 are trust/quality-matchable" in text


@pytest.mark.fast
def test_render_zero_service_bucket_line_present():
    """'0 are service/attribute-matchable' line is rendered when b1 = 0."""
    scored = [
        _scored("r_001", "trust_quality_matchable"),
        _scored("r_002", "low_retrievability"),
    ]
    report = _build(scored_reviews=scored, corpus_stats=_stats(2, 0, 1, 1))
    text = render_text_report(report)
    assert "• 0 are service/attribute-matchable" in text


@pytest.mark.fast
def test_render_zero_low_bucket_line_present():
    """'0 are low-retrievability' is rendered when b3 = 0."""
    scored = [
        _scored("r_001", "service_attribute_matchable"),
        _scored("r_002", "trust_quality_matchable"),
    ]
    report = _build(scored_reviews=scored, corpus_stats=_stats(2, 1, 1, 0))
    text = render_text_report(report)
    assert "• 0 are low-retrievability" in text


# ── render_text_report: thin corpus warning ──────────────────────────────────

@pytest.mark.fast
def test_render_thin_corpus_warning_included():
    """Thin corpus note appears when total_reviews < 20."""
    scored = [_scored(f"r_{i:03}", "low_retrievability") for i in range(1, 6)]
    report = _build(scored_reviews=scored, corpus_stats=_stats(5, 0, 0, 5), metadata=_metadata(5, 5))
    text = render_text_report(report)
    assert "fewer than 20 reviews" in text


@pytest.mark.fast
def test_render_thin_corpus_boundary_19_triggers_warning():
    """Exactly 19 reviews triggers the thin corpus note (boundary check)."""
    scored = [_scored(f"r_{i:03}", "low_retrievability") for i in range(1, 20)]
    report = _build(scored_reviews=scored, corpus_stats=_stats(19, 0, 0, 19), metadata=_metadata(19, 19))
    text = render_text_report(report)
    assert "fewer than 20 reviews" in text


@pytest.mark.fast
def test_render_thin_corpus_boundary_20_no_warning():
    """Exactly 20 reviews does NOT trigger the thin corpus note (boundary check)."""
    scored = [_scored(f"r_{i:03}", "low_retrievability") for i in range(1, 21)]
    report = _build(scored_reviews=scored, corpus_stats=_stats(20, 0, 0, 20), metadata=_metadata(20, 20))
    text = render_text_report(report)
    assert "fewer than 20 reviews" not in text


@pytest.mark.fast
def test_render_large_corpus_no_thin_warning():
    """No thin corpus note in a typical 25-review corpus."""
    scored = [_scored(f"r_{i:03}", "low_retrievability") for i in range(1, 26)]
    report = _build(scored_reviews=scored, corpus_stats=_stats(25, 0, 0, 25), metadata=_metadata(25, 25))
    text = render_text_report(report)
    assert "fewer than 20 reviews" not in text


# ── render_text_report: low profile confidence note ─────────────────────────

@pytest.mark.fast
def test_render_low_profile_confidence_note_included():
    """Low profile confidence note appears when profile confidence is 'low'."""
    report = _build(profile=_profile("low"))
    text = render_text_report(report)
    assert "too thin or generic" in text


@pytest.mark.fast
def test_render_low_profile_confidence_note_is_provisional():
    """Low profile confidence note uses the word 'provisional'."""
    report = _build(profile=_profile("low"))
    text = render_text_report(report)
    assert "provisional" in text


@pytest.mark.fast
def test_render_medium_profile_confidence_no_low_note():
    """Low profile confidence note is absent when confidence is 'medium'."""
    report = _build(profile=_profile("medium"))
    text = render_text_report(report)
    assert "too thin or generic" not in text


@pytest.mark.fast
def test_render_high_profile_confidence_no_low_note():
    """Low profile confidence note is absent when confidence is 'high'."""
    report = _build(profile=_profile("high"))
    text = render_text_report(report)
    assert "too thin or generic" not in text


# ── render_text_report: wording rules ────────────────────────────────────────

@pytest.mark.fast
def test_render_wording_no_good_enough():
    """'good enough' never appears — it frames reviews as passing/failing a standard."""
    report = _build()
    text = render_text_report(report)
    assert "good enough" not in text.lower()


@pytest.mark.fast
def test_render_wording_no_bad():
    """'bad' never appears — the tool does not judge review quality."""
    report = _build()
    text = render_text_report(report)
    assert "bad" not in text.lower()


@pytest.mark.fast
def test_render_wording_no_improve():
    """'improve' never appears — the tool reports structure, not remediation."""
    report = _build()
    text = render_text_report(report)
    assert "improve" not in text.lower()


# ── render_text_report: structural completeness ──────────────────────────────

@pytest.mark.fast
def test_render_all_section_headers_present():
    """Rendered report contains all six section headers."""
    report = _build()
    text = render_text_report(report)
    for header in (
        "HEADLINE",
        "DIMENSION COVERAGE",
        "BUSINESS PROFILE",
        "EXAMPLES",
        "LABELING CONFIDENCE",
        "CAVEATS",
    ):
        assert header in text, f"Missing section header: {header}"


@pytest.mark.fast
def test_render_review_text_appears_in_examples():
    """Review text appears in the EXAMPLES section (truncated if needed)."""
    unique_text = "Exceptionally specific croissant with Normandy butter and sea salt"
    scored = [
        _scored("r_001", "service_attribute_matchable", text=unique_text),
        _scored("r_002", "trust_quality_matchable"),
        _scored("r_003", "low_retrievability"),
    ]
    report = _build(scored_reviews=scored)
    text = render_text_report(report)
    assert unique_text in text


@pytest.mark.fast
def test_render_all_example_bucket_labels_present_even_when_empty():
    """All three example bucket labels appear even when some buckets have no reviews."""
    scored = [_scored("r_001", "low_retrievability"), _scored("r_002", "low_retrievability")]
    report = _build(scored_reviews=scored, corpus_stats=_stats(2, 0, 0, 2))
    text = render_text_report(report)
    assert "Service/attribute-matchable" in text
    assert "Trust/quality-matchable" in text
    assert "Low-retrievability" in text


# ── render_html_report: structural ──────────────────────────────────────────

@pytest.mark.fast
def test_html_starts_with_doctype():
    """render_html_report returns a string that starts with <!DOCTYPE html>."""
    report = _build()
    assert render_html_report(report).startswith("<!DOCTYPE html>")


@pytest.mark.fast
def test_html_contains_headline_percentage():
    """The formatted ai_visibility_pct appears verbatim in the HTML output."""
    scored = [
        _scored("r_001", "service_attribute_matchable"),
        _scored("r_002", "service_attribute_matchable"),
        _scored("r_003", "low_retrievability"),
    ]
    report = _build(scored_reviews=scored, corpus_stats=_stats(3, 2, 0, 1))
    # ai_pct = (2 + 0) / 3 * 100 = 66.7
    assert "66.7%" in render_html_report(report)


# ── render_html_report: framing rules ───────────────────────────────────────

@pytest.mark.fast
def test_html_framing_no_bad():
    """'bad' never appears in the rendered HTML — the tool does not judge quality."""
    assert "bad" not in render_html_report(_build()).lower()


@pytest.mark.fast
def test_html_framing_no_improve():
    """'improve' never appears in the rendered HTML."""
    assert "improve" not in render_html_report(_build()).lower()


@pytest.mark.fast
def test_html_framing_no_good_enough():
    """'good enough' never appears in the rendered HTML."""
    assert "good enough" not in render_html_report(_build()).lower()


# ── render_html_report: SVG chart elements ──────────────────────────────────

@pytest.mark.fast
def test_html_svg_bucket_bar_present():
    """HTML output contains the bucket distribution stacked-bar SVG."""
    assert 'aria-label="Bucket distribution stacked bar"' in render_html_report(_build())


@pytest.mark.fast
def test_html_svg_dimension_bars_present():
    """HTML output contains the dimension coverage SVG."""
    assert 'aria-label="Dimension coverage chart"' in render_html_report(_build())


@pytest.mark.fast
def test_html_svg_rect_elements_present():
    """SVG charts use <rect> elements drawn from the data."""
    assert "<rect" in render_html_report(_build())


# ── render_html_report: content completeness ────────────────────────────────

@pytest.mark.fast
def test_html_all_bucket_names_present():
    """All three bucket names appear in the HTML output."""
    out = render_html_report(_build()).lower()
    assert "service/attribute-matchable" in out
    assert "trust/quality-matchable" in out
    assert "low-retrievability" in out


@pytest.mark.fast
def test_html_thin_corpus_note_present():
    """Thin corpus note appears in the HTML when total_reviews < 20."""
    scored = [_scored(f"r_{i:03}", "low_retrievability") for i in range(1, 6)]
    report = _build(scored_reviews=scored, corpus_stats=_stats(5, 0, 0, 5), metadata=_metadata(5, 5))
    assert "fewer than 20 reviews" in render_html_report(report)


@pytest.mark.fast
def test_html_thin_corpus_note_absent_at_20():
    """Thin corpus note is absent when total_reviews == 20."""
    scored = [_scored(f"r_{i:03}", "low_retrievability") for i in range(1, 21)]
    report = _build(scored_reviews=scored, corpus_stats=_stats(20, 0, 0, 20), metadata=_metadata(20, 20))
    assert "fewer than 20 reviews" not in render_html_report(report)


@pytest.mark.fast
def test_html_low_profile_confidence_note_present():
    """Low profile confidence note appears in the HTML when confidence is 'low'."""
    report = _build(profile=_profile("low"))
    assert "too thin or generic" in render_html_report(report)


@pytest.mark.fast
def test_html_example_review_text_appears():
    """A distinctive review text appears in the HTML examples section."""
    unique = "Exceptional almond croissant with Normandy butter and Maldon salt flakes"
    scored = [
        _scored("r_001", "service_attribute_matchable", text=unique),
        _scored("r_002", "trust_quality_matchable"),
        _scored("r_003", "low_retrievability"),
    ]
    report = _build(scored_reviews=scored)
    assert unique in render_html_report(report)
