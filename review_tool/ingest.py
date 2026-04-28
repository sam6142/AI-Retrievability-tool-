"""Stage 1: Load and normalise reviews from CSV or JSON."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import TypedDict

import pandas as pd

logger = logging.getLogger(__name__)

# Matches spreadsheet error tokens produced by broken scrapers: #ERROR!, #N/A, #DIV/0!, etc.
_SPREADSHEET_ERROR = re.compile(r"^#[\w/!?]+$")
# A junk text must have at least one alphanumeric character to count as a real word.
_HAS_ALNUM = re.compile(r"[a-zA-Z0-9]")


class Review(TypedDict):
    review_id: str
    text: str
    rating: int | None
    date: str | None


def _is_junk(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if _SPREADSHEET_ERROR.match(stripped):
        return True
    if not _HAS_ALNUM.search(stripped):
        # entirely emoji, punctuation, or other non-word characters
        return True
    if len(stripped.split()) < 3:
        return True
    return False


def _normalise_rating(value: object) -> int | None:
    try:
        r = int(float(str(value)))
        return r if 1 <= r <= 5 else None
    except (ValueError, TypeError):
        return None


def _normalise_date(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s and s.lower() not in ("nan", "none", "") else None


def _try_read_csv(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return pd.read_csv(path, dtype=str, keep_default_na=False, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode {path} — tried utf-8, latin-1, cp1252")


def _load_csv(path: Path) -> list[Review]:
    try:
        df = _try_read_csv(path)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Cannot parse CSV at {path}: {exc}") from exc

    df.columns = [c.strip().lower() for c in df.columns]

    if "review_text" not in df.columns:
        raise ValueError(
            f"CSV missing required column 'review_text' (found: {list(df.columns)})"
        )

    dropped = 0
    reviews: list[Review] = []
    for _, row in df.iterrows():
        text = str(row.get("review_text", "")).strip()
        if _is_junk(text):
            dropped += 1
            continue
        reviews.append(
            Review(
                review_id=str(row.get("review_id", "")).strip() or "",
                text=text,
                rating=_normalise_rating(row.get("rating")),
                date=_normalise_date(row.get("date")),
            )
        )
    if dropped:
        logger.info("Dropped %d row(s) with empty/junk text.", dropped)
    return reviews


def _try_read_json(path: Path) -> str:
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode {path} — tried utf-8, latin-1, cp1252")


def _load_json(path: Path) -> list[Review]:
    text = _try_read_json(path)
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Cannot parse JSON at {path}: {exc}") from exc

    if not isinstance(raw, list):
        raise ValueError(
            f"Expected a JSON array at top level, got {type(raw).__name__}"
        )

    dropped = 0
    reviews: list[Review] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("review_text", "")).strip()
        if _is_junk(text):
            dropped += 1
            continue
        reviews.append(
            Review(
                review_id=str(entry.get("review_id", "")).strip() or "",
                text=text,
                rating=_normalise_rating(entry.get("rating")),
                date=_normalise_date(entry.get("date")),
            )
        )
    if dropped:
        logger.info("Dropped %d row(s) with empty/junk text.", dropped)
    return reviews


def _dedup(reviews: list[Review]) -> list[Review]:
    seen: set[str] = set()
    out: list[Review] = []
    for r in reviews:
        key = r["text"].lower()
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _resolve_ids(reviews: list[Review]) -> list[Review]:
    """Preserve unique user-provided IDs; assign r_NNN only to blank or duplicate entries.

    Walks reviews in order. Any review whose ID is blank or already taken gets the
    next available r_NNN slot. Unique user-provided IDs are never touched.
    Logs a warning if any regeneration was necessary.
    """
    seen: set[str] = set()
    regen_counter = 0
    # Track all unique user-provided IDs upfront so generated IDs don't collide with them.
    provided = {r["review_id"] for r in reviews if r["review_id"]}

    # Next available r_NNN that isn't already claimed by a user-provided ID.
    seq = 1

    def _next_generated() -> str:
        nonlocal seq
        candidate = f"r_{seq:03d}"
        while candidate in provided:
            seq += 1
            candidate = f"r_{seq:03d}"
        seq += 1
        return candidate

    for r in reviews:
        rid = r["review_id"]
        if not rid or rid in seen:
            r["review_id"] = _next_generated()
            provided.add(r["review_id"])
            regen_counter += 1
        seen.add(r["review_id"])

    if regen_counter:
        logger.warning(
            "%d review_id(s) were blank or duplicated — assigned generated IDs.",
            regen_counter,
        )
    return reviews


def ingest(path: str | Path) -> list[Review]:
    """Load, clean, dedup, and ID-stamp reviews from *path*.

    Accepts CSV or JSON (auto-detected from extension).
    Raises FileNotFoundError if the file is missing.
    Raises ValueError if the file is empty, malformed, or has an unsupported extension.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Reviews file not found: {p}")

    suffix = p.suffix.lower()
    if suffix == ".csv":
        reviews = _load_csv(p)
    elif suffix == ".json":
        reviews = _load_json(p)
    else:
        raise ValueError(f"Unsupported file type '{suffix}'. Expected .csv or .json.")

    if not reviews:
        raise ValueError(f"No reviews found in {p}")

    before_dedup = len(reviews)
    reviews = _dedup(reviews)
    removed = before_dedup - len(reviews)
    if removed:
        logger.info("Removed %d duplicate review(s).", removed)

    reviews = _resolve_ids(reviews)

    logger.info("Loaded %d review(s) from %s.", len(reviews), p.name)
    return reviews
