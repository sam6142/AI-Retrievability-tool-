"""CLI entry point for the review retrievability diagnostic tool.

Usage:
    python -m review_tool.analyze --reviews path/to/reviews.csv --output reports/
    review-tool --reviews path/to/reviews.csv --output reports/
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer

from review_tool.aggregate import ScoredReview, aggregate
from review_tool.ingest import ingest
from review_tool.llm_client import LLMAuthError
from review_tool.profile import infer_profile
from review_tool.report import build_report, render_text_report, write_report
from review_tool.scorer import score_corpus

logger = logging.getLogger(__name__)

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


def _count_raw_rows(path: Path) -> int:
    """Quick count of raw rows in the input file before ingest cleaning."""
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            import pandas as pd
            for enc in ("utf-8", "latin-1", "cp1252"):
                try:
                    return len(pd.read_csv(path, dtype=str, keep_default_na=False, encoding=enc))
                except UnicodeDecodeError:
                    continue
        elif suffix == ".json":
            for enc in ("utf-8", "latin-1", "cp1252"):
                try:
                    raw = json.loads(path.read_text(encoding=enc))
                    return len(raw) if isinstance(raw, list) else 0
                except UnicodeDecodeError:
                    continue
    except Exception as exc:
        logger.warning("Could not count raw rows in %s: %s", path, exc)
    return 0


@app.command()
def main(
    reviews: Path = typer.Option(..., "--reviews", help="Path to reviews CSV or JSON file"),
    output: Path = typer.Option(..., "--output", help="Output directory for report files"),
    oneliner: Optional[str] = typer.Option(
        None, "--oneliner", help="Optional one-line business description (~5–30 words)"
    ),
    model: str = typer.Option(
        "claude-haiku-4-5-20251001", "--model", help="Anthropic model ID for LLM calls"
    ),
    profile_sample_size: int = typer.Option(
        30, "--profile-sample-size", help="Reviews to sample for business profile inference"
    ),
) -> None:
    """Run the review retrievability diagnostic pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    try:
        # ── Stage 1: Ingest ──────────────────────────────────────────────────
        typer.echo(f"[1/6] Ingesting reviews from {reviews}...")
        raw_count = _count_raw_rows(reviews)
        review_list = ingest(reviews)
        clean_count = len(review_list)
        dropped = raw_count - clean_count if raw_count >= clean_count else 0
        typer.echo(f"      {clean_count} reviews loaded ({dropped} dropped after cleaning).")

        # ── Stage 2: Business profile inference ─────────────────────────────
        actual_sample = min(profile_sample_size, clean_count)
        typer.echo(f"[2/6] Inferring business profile from {actual_sample}-review sample...")
        profile = infer_profile(review_list, oneliner=oneliner, sample_size=profile_sample_size)

        # ── Stage 3: Per-review scoring ──────────────────────────────────────
        typer.echo(f"[3/6] Scoring {clean_count} reviews ({model})...")

        def progress_cb(index: int, total: int, _sr: ScoredReview) -> None:
            typer.echo(f"\r      ({index}/{total})", nl=False)
            if index == total:
                typer.echo()

        scored = score_corpus(
            review_list, profile, model=model, progress_callback=progress_cb
        )

        # ── Stage 4: Classification (deterministic, inside score_corpus) ─────
        typer.echo("[4/6] Classification done (deterministic, no LLM call).")

        # ── Stage 5: Aggregation ─────────────────────────────────────────────
        typer.echo("[5/6] Aggregating corpus statistics...")
        stats = aggregate(scored)

        # ── Stage 6: Report ──────────────────────────────────────────────────
        typer.echo("[6/6] Generating report...")
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        metadata = {
            "tool_version": "0.1.0",
            "rubric_version": "v2",
            "generated_at": generated_at,
            "input_file": str(reviews),
            "input_review_count_raw": raw_count,
            "input_review_count_after_cleaning": clean_count,
            "user_oneliner": oneliner,
        }

        report = build_report(review_list, scored, profile, stats, metadata)
        write_report(report, output)

        # ── Headline summary ─────────────────────────────────────────────────
        ai_pct = stats["ai_visibility_pct"]
        by_b = stats["by_bucket"]
        typer.echo(
            f"\nResults written to {output}/\n"
            f"  Combined LLM-retrievability: {ai_pct:.1f}%  "
            f"({by_b['service_attribute_matchable']} service/attr-matchable  +  "
            f"{by_b['trust_quality_matchable']} trust/quality-matchable  out of "
            f"{stats['total_reviews']} reviews)"
        )

    except FileNotFoundError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    except LLMAuthError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)
    except Exception as exc:
        logger.exception("Unexpected pipeline error")
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
