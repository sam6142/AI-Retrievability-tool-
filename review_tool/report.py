"""Stage 6: Report generation — JSON output and deterministic text/HTML summaries.

build_report()        → assemble + validate the full CorpusReport dict
render_text_report()  → produce report.txt from the dict (no LLM calls)
render_html_report()  → produce self-contained report.html (no LLM calls)
write_report()        → write report.json, report.txt, and report.html to disk
"""

from __future__ import annotations

import html as _html
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
# HTML rendering helpers
# ---------------------------------------------------------------------------

_HTML_CSS = """\
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #000000;
  color: #eeeeee;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 15px;
  line-height: 1.65;
  max-width: 860px;
  margin: 0 auto;
  padding: 48px 28px;
}
header { padding-bottom: 32px; border-bottom: 1px solid #333333; }
h1 { color: #FFE600; font-size: 1.6rem; font-weight: 700; letter-spacing: .03em; margin-bottom: 10px; }
h2 { color: #FFE600; font-size: .9rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 18px; }
h3 { color: #eeeeee; font-size: .9rem; font-weight: 600; margin: 18px 0 8px; }
section { border-top: 1px solid #333333; padding: 36px 0; }
p { margin-bottom: 14px; }
p:last-child { margin-bottom: 0; }
strong { color: #eeeeee; }
.yellow { color: #FFE600; font-weight: 700; }
.meta { display: flex; flex-wrap: wrap; gap: 8px 24px; font-size: 13px; color: #999999; }
.meta strong { color: #eeeeee; }
.headline-pct {
  font-size: clamp(4rem, 12vw, 7rem);
  font-weight: 700;
  color: #FFE600;
  line-height: 1;
  margin: 20px 0 6px;
}
.headline-label { font-size: 1rem; margin-bottom: 24px; }
.bucket-counts { display: flex; flex-direction: column; gap: 6px; margin-bottom: 18px; }
.bucket-count { font-size: .95rem; }
.bucket-count .count { color: #FFE600; font-weight: 700; display: inline-block; min-width: 2.5em; }
.chart-legend { display: flex; flex-wrap: wrap; gap: 10px 24px; margin-top: 14px; font-size: 13px; }
.legend-item { display: flex; align-items: center; gap: 8px; }
.legend-swatch { width: 14px; height: 14px; border-radius: 2px; flex-shrink: 0; display: inline-block; }
ul { list-style: none; padding: 0; margin-bottom: 12px; }
ul li { padding-left: 18px; position: relative; margin-bottom: 4px; }
ul li::before { content: "\\2022"; color: #FFE600; position: absolute; left: 0; }
.profile-confidence { color: #FFE600; font-weight: 700; }
.note { border-left: 2px solid #FFE600; padding: 8px 14px; color: #bbbbbb; font-size: .9rem; margin: 16px 0; }
.example { margin-bottom: 28px; }
.example-bucket {
  color: #FFE600;
  font-size: .8rem;
  font-weight: 700;
  letter-spacing: .1em;
  text-transform: uppercase;
  margin-bottom: 10px;
}
.example-card { border: 1px solid #333333; padding: 14px 16px; margin-bottom: 10px; }
.example-id { font-size: .78rem; color: #888888; margin-bottom: 6px; }
.example-text { font-size: .95rem; font-style: italic; margin-bottom: 10px; }
.example-labels { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.label-chip { font-size: .72rem; padding: 2px 7px; background: #111111; border: 1px solid #333333; color: #666666; }
.label-chip.active { border-color: #FFE600; color: #FFE600; }
.example-rationale { font-size: .78rem; color: #777777; line-height: 1.5; }
.example-rationale strong { color: #999999; }
footer { border-top: 1px solid #333333; padding-top: 28px; font-size: .85rem; color: #666666; }
.footer-fixed { margin-top: 10px; font-style: italic; color: #555555; }
"""


def _h(text: str) -> str:
    """Escape text for safe inclusion in HTML content."""
    return _html.escape(str(text), quote=False)


def _ha(text: str) -> str:
    """Escape text for safe inclusion in an HTML attribute value."""
    return _html.escape(str(text), quote=True)


def _html_bullet_list(items: list[str]) -> str:
    if not items:
        return "<ul><li><em>(none identified)</em></li></ul>"
    return "<ul>" + "".join(f"<li>{_h(item)}</li>" for item in items) + "</ul>"


def _chip(dim_name: str, score: int) -> str:
    cls = "label-chip active" if score >= 1 else "label-chip"
    return f'<span class="{cls}">{_h(dim_name)}={score}</span>'


def _svg_bucket_bar(b1: int, b2: int, b3: int, total: int) -> str:
    """Inline SVG stacked horizontal bar for bucket distribution."""
    if total == 0:
        return "<p><em>(no data)</em></p>"
    W, H = 600, 52
    w1 = b1 / total * W
    w2 = b2 / total * W
    w3 = b3 / total * W
    x2 = w1
    x3 = w1 + w2
    _LABEL_MIN_W = 70

    segs: list[str] = []
    for w, x, fill, txt_fill, count, abbr in [
        (w1, 0.0,   "#FFE600", "#000000", b1, "SAM"),
        (w2, x2,    "#888888", "#000000", b2, "TQM"),
        (w3, x3,    "#333333", "#EEEEEE", b3, "LR"),
    ]:
        if w <= 0:
            continue
        segs.append(
            f'<rect x="{x:.2f}" y="0" width="{w:.2f}" height="{H}" fill="{fill}"/>'
        )
        if w >= _LABEL_MIN_W:
            cx = x + w / 2
            segs.append(
                f'<text x="{cx:.1f}" y="{H // 2 + 5}" text-anchor="middle" '
                f'fill="{txt_fill}" font-size="12" font-weight="600" '
                f'font-family="system-ui,sans-serif">{count} {abbr}</text>'
            )

    return (
        '<svg viewBox="0 0 600 52" xmlns="http://www.w3.org/2000/svg" '
        'style="width:100%;max-width:600px;display:block;border:1px solid #333333" '
        'role="img" aria-label="Bucket distribution stacked bar">'
        + "".join(segs)
        + "</svg>"
    )


def _svg_dimension_bars(dim: dict[str, float], weakest: str) -> str:
    """Inline SVG with five horizontal bars for dimension coverage."""
    DIMS: list[tuple[str, str]] = [
        ("service",           "Service"),
        ("attributes",        "Attributes"),
        ("outcome",           "Outcome"),
        ("occasion",          "Occasion"),
        ("descriptive_depth", "Depth"),
    ]
    LABEL_W, BAR_W, PCT_W = 100, 320, 55
    BAR_H, ROW_H = 22, 38
    W = LABEL_W + BAR_W + PCT_W
    H = len(DIMS) * ROW_H - (ROW_H - BAR_H)

    rows: list[str] = []
    for i, (key, label) in enumerate(DIMS):
        pct = dim.get(key, 0.0)
        fill_w = max(0.0, min(pct / 100.0 * BAR_W, float(BAR_W)))
        y = i * ROW_H
        text_y = y + BAR_H // 2 + 5
        is_weakest = key == weakest
        lbl_color = "#FFE600" if is_weakest else "#EEEEEE"
        suffix = " ◄" if is_weakest else ""

        rows.append(
            f'<text x="{LABEL_W - 8}" y="{text_y}" text-anchor="end" '
            f'fill="{lbl_color}" font-size="13" font-family="system-ui,sans-serif">'
            f"{_h(label)}{suffix}</text>"
            f'<rect x="{LABEL_W}" y="{y}" width="{BAR_W}" height="{BAR_H}" fill="#333333" rx="2"/>'
            f'<rect x="{LABEL_W}" y="{y}" width="{fill_w:.2f}" height="{BAR_H}" fill="#FFE600" rx="2"/>'
            f'<text x="{LABEL_W + BAR_W + 8}" y="{text_y}" '
            f'fill="#EEEEEE" font-size="13" font-family="system-ui,sans-serif">{pct:.1f}%</text>'
        )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;max-width:{W}px;display:block" '
        f'role="img" aria-label="Dimension coverage chart">'
        + "".join(rows)
        + "</svg>"
    )


def _html_examples_section(
    epb: dict[str, list[str]],
    lookup: dict[str, dict],
) -> str:
    BUCKET_LABELS = [
        ("service_attribute_matchable", "Service/attribute-matchable"),
        ("trust_quality_matchable",     "Trust/quality-matchable"),
        ("low_retrievability",          "Low-retrievability"),
    ]
    DIMS = ("service", "attributes", "outcome", "occasion", "descriptive_depth")
    parts: list[str] = []

    for bk, bk_label in BUCKET_LABELS:
        ids: list[str] = epb.get(bk, [])
        cards: list[str] = []

        if ids:
            for rid in ids:
                sr = lookup.get(rid)
                if not sr:
                    continue
                raw_text: str = sr.get("text", "")
                truncated = raw_text if len(raw_text) <= 120 else raw_text[:120] + "..."
                labels: dict = sr.get("labels", {})
                rationale: dict = sr.get("rationale", {})
                confidence: str = sr.get("confidence", "")

                chips = "".join(_chip(d, labels.get(d, 0)) for d in DIMS)
                rat_lines = "".join(
                    f"<div><strong>{_h(d)}:</strong> {_h(rationale.get(d, ''))}</div>"
                    for d in DIMS
                    if rationale.get(d)
                )
                cards.append(
                    f'<div class="example-card">'
                    f'<div class="example-id">[{_h(rid)}] &middot; confidence: {_h(confidence)}</div>'
                    f'<div class="example-text">&ldquo;{_h(truncated)}&rdquo;</div>'
                    f'<div class="example-labels">{chips}</div>'
                    f'<div class="example-rationale">{rat_lines}</div>'
                    f"</div>"
                )
        else:
            cards.append("<p>(no reviews in this bucket)</p>")

        parts.append(
            f'<div class="example">'
            f'<div class="example-bucket">{_h(bk_label)}</div>'
            + "".join(cards)
            + "</div>"
        )

    return "\n".join(parts)


def render_html_report(report: dict) -> str:
    """Build a self-contained HTML report from a validated CorpusReport dict.

    Returns a complete HTML string with inline CSS and inline SVG charts.
    No external dependencies, no CDN links, no JavaScript.
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
    h_cnt: int = conf["high"]
    m_cnt: int = conf["medium"]
    l_cnt: int = conf["low"]

    date_str = (meta.get("generated_at") or "")[:10]
    business_type: str = bp.get("business_type", "")
    bp_confidence: str = bp.get("confidence", "")
    lookup: dict[str, dict] = {sr["review_id"]: sr for sr in scored}

    safe_total = total if total > 0 else 1
    h_pct = h_cnt / safe_total * 100
    m_pct = m_cnt / safe_total * 100
    l_pct = l_cnt / safe_total * 100

    # Pre-render variable HTML blocks so the f-string stays free of complex expressions.
    bucket_bar_svg     = _svg_bucket_bar(b1, b2, b3, total)
    dimension_bars_svg = _svg_dimension_bars(dim, weakest)
    examples_html      = _html_examples_section(epb, lookup)
    services_html      = _html_bullet_list(bp.get("inferred_services", []))
    attributes_html    = _html_bullet_list(bp.get("inferred_attributes", []))
    contexts_html      = _html_bullet_list(bp.get("inferred_customer_contexts", []))

    thin_note = (
        '<div class="note">NOTE: This corpus contains fewer than 20 reviews. '
        "Findings are provisional. Larger corpora produce more reliable "
        "retrievability diagnostics.</div>"
        if total < 20
        else ""
    )
    low_conf_note = (
        '<div class="note">NOTE: The review corpus is too thin or generic to '
        "characterize this business reliably. The profile above represents a "
        "best-effort inference; the diagnostic that follows should be read as "
        "provisional.</div>"
        if bp_confidence == "low"
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Review Retrievability Report &#x2014; {_ha(business_type)}</title>
<style>
{_HTML_CSS}
</style>
</head>
<body>

<header>
  <h1>Review Retrievability Report</h1>
  <div class="meta">
    <span>Business: <strong>{_h(business_type)}</strong></span>
    <span>Reviews analyzed: <strong>{total}</strong></span>
    <span>Generated: <strong>{_h(date_str)}</strong></span>
  </div>
</header>

<section id="headline">
  <h2>Headline</h2>
  {thin_note}
  <div class="headline-pct">{ai_pct:.1f}%</div>
  <div class="headline-label">Combined LLM-retrievability</div>
  <div class="bucket-counts">
    <div class="bucket-count"><span class="count">{b1}</span> service/attribute-matchable</div>
    <div class="bucket-count"><span class="count">{b2}</span> trust/quality-matchable</div>
    <div class="bucket-count"><span class="count">{b3}</span> low-retrievability</div>
  </div>
  <p>The corpus is currently positioned to surface this business for specific-service and
  trust-quality LLM queries on roughly {ai_pct:.1f}% of its reviews. The remaining
  {b3} reviews do not carry sufficient semantic content for LLM retrieval, though they
  continue to function for star ratings and social proof.</p>
</section>

<p style="font-size:13px;color:#999999;margin:0 0 32px;">v1 prompt &#x2014; known calibration limitations: outcome dimension over-scores on consumption businesses (96% on this corpus vs ~16% expected). See docs/PROMPT_ITERATION.md for prompt-iteration plan.</p>

<section id="distribution">
  <h2>Bucket Distribution</h2>
  {bucket_bar_svg}
  <div class="chart-legend">
    <div class="legend-item"><span class="legend-swatch" style="background:#FFE600"></span>Service/attribute-matchable ({b1})</div>
    <div class="legend-item"><span class="legend-swatch" style="background:#888888"></span>Trust/quality-matchable ({b2})</div>
    <div class="legend-item"><span class="legend-swatch" style="background:#333333;outline:1px solid #555555"></span>Low-retrievability ({b3})</div>
  </div>
</section>

<section id="dimensions">
  <h2>Dimension Coverage</h2>
  <p>Percent of reviews mentioning each dimension at least generically.
  Weakest: <span class="yellow">{_h(weakest)}</span></p>
  {dimension_bars_svg}
</section>

<section id="profile">
  <h2>Business Profile</h2>
  <p>Type: <strong>{_h(business_type)}</strong> &#x2014;
  Profile confidence: <span class="profile-confidence">{_h(bp_confidence)}</span></p>
  <h3>Services</h3>
  {services_html}
  <h3>Attributes</h3>
  {attributes_html}
  <h3>Customer contexts</h3>
  {contexts_html}
  {low_conf_note}
</section>

<section id="examples">
  <h2>Examples</h2>
  {examples_html}
</section>

<section id="confidence">
  <h2>Labeling Confidence</h2>
  <p>The labeler self-reported confidence on each review:</p>
  <ul>
    <li>High confidence: {h_cnt} ({h_pct:.1f}%)</li>
    <li>Medium confidence: {m_cnt} ({m_pct:.1f}%)</li>
    <li>Low confidence: {l_cnt} ({l_pct:.1f}%)</li>
  </ul>
  <p>Low-confidence assignments are reviews where the rubric is genuinely ambiguous.
  They are flagged in the JSON output for optional human review.</p>
</section>

<footer>
  <p>This is a prototype diagnostic. Findings are based on the provided review corpus
  alone and do not account for review recency, geographic relevance, or query-specific
  retrieval behavior. The retrieval bucket assignments reflect what each review&#8217;s
  content enables, not whether the review is &#8220;good.&#8221;</p>
  <p class="footer-fixed">Retrievability is a structural property of review content &#x2014;
  not a judgment of review quality.</p>
</footer>

</body>
</html>"""


# ---------------------------------------------------------------------------
# File output
# ---------------------------------------------------------------------------

def write_report(report: dict, output_dir: Path) -> None:
    """Write report.json, report.txt, and report.html to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "report.json"
    txt_path  = output_dir / "report.txt"
    html_path = output_dir / "report.html"

    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Wrote %s", json_path)

    txt_path.write_text(render_text_report(report), encoding="utf-8")
    logger.info("Wrote %s", txt_path)

    html_path.write_text(render_html_report(report), encoding="utf-8")
    logger.info("Wrote %s", html_path)
