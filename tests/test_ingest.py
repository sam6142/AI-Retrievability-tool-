"""Tests for review_tool.ingest — CSV/JSON loading and cleaning."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from review_tool.ingest import ingest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _write_csv(path: Path, rows: list[str], header: str = "review_text") -> Path:
    path.write_text("\n".join([header] + rows) + "\n", encoding="utf-8")
    return path


def _write_json(path: Path, entries: list[dict]) -> Path:
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Happy path — real fixture files
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_load_csv_fixture(fixtures_dir: Path) -> None:
    reviews = ingest(fixtures_dir / "milk_bar_sample.csv")
    assert 95 <= len(reviews) <= 100, f"expected 95-100 reviews, got {len(reviews)}"


@pytest.mark.fast
def test_load_json_fixture(fixtures_dir: Path) -> None:
    reviews = ingest(fixtures_dir / "milk_bar_sample.json")
    assert 95 <= len(reviews) <= 100, f"expected 95-100 reviews, got {len(reviews)}"


@pytest.mark.fast
def test_review_shape_csv(fixtures_dir: Path) -> None:
    reviews = ingest(fixtures_dir / "milk_bar_sample.csv")
    r = reviews[0]
    assert "review_id" in r
    assert "text" in r
    assert "rating" in r
    assert "date" in r
    assert "review_text" not in r, "internal field must be 'text', not 'review_text'"
    assert r["text"] != ""


@pytest.mark.fast
def test_review_shape_json(fixtures_dir: Path) -> None:
    reviews = ingest(fixtures_dir / "milk_bar_sample.json")
    r = reviews[0]
    assert r["review_id"] != ""
    assert len(r["text"].split()) >= 3


@pytest.mark.fast
def test_all_ids_unique_csv(fixtures_dir: Path) -> None:
    reviews = ingest(fixtures_dir / "milk_bar_sample.csv")
    ids = [r["review_id"] for r in reviews]
    assert len(ids) == len(set(ids)), "review_ids must be unique"


@pytest.mark.fast
def test_all_ids_unique_json(fixtures_dir: Path) -> None:
    reviews = ingest(fixtures_dir / "milk_bar_sample.json")
    ids = [r["review_id"] for r in reviews]
    assert len(ids) == len(set(ids)), "review_ids must be unique"


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_deduplication_keeps_first(tmp_path: Path) -> None:
    csv = _write_csv(
        tmp_path / "dup.csv",
        [
            '"Amazing cereal milk soft serve, absolutely worth it"',
            '"Amazing cereal milk soft serve, absolutely worth it"',  # exact duplicate
            '"Birthday cake truffles are unreal and always fresh"',
        ],
    )
    reviews = ingest(csv)
    assert len(reviews) == 2


@pytest.mark.fast
def test_deduplication_case_insensitive(tmp_path: Path) -> None:
    csv = _write_csv(
        tmp_path / "dup_case.csv",
        [
            '"Amazing cereal milk soft serve absolutely worth it"',
            '"amazing cereal milk soft serve absolutely worth it"',  # same text, different case
        ],
    )
    reviews = ingest(csv)
    assert len(reviews) == 1


# ---------------------------------------------------------------------------
# Junk filtering
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_error_token_is_dropped(tmp_path: Path) -> None:
    csv = _write_csv(
        tmp_path / "err.csv",
        [
            "#ERROR!",
            '"Great birthday cake truffles, so fresh and moist"',
        ],
    )
    reviews = ingest(csv)
    assert len(reviews) == 1
    assert "ERROR" not in reviews[0]["text"]


@pytest.mark.fast
def test_spreadsheet_error_variants_dropped(tmp_path: Path) -> None:
    csv = _write_csv(
        tmp_path / "errors.csv",
        [
            "#N/A",
            "#VALUE!",
            "#REF!",
            '"Crack pie is absolutely worth every calorie every single time"',
        ],
    )
    reviews = ingest(csv)
    assert len(reviews) == 1


@pytest.mark.fast
def test_two_word_review_is_dropped(tmp_path: Path) -> None:
    csv = _write_csv(
        tmp_path / "short.csv",
        [
            '"Great place"',                                          # 2 words — dropped
            '"Cereal milk soft serve is the best dessert in Vegas"',  # kept
        ],
    )
    reviews = ingest(csv)
    assert len(reviews) == 1


@pytest.mark.fast
def test_one_word_review_is_dropped(tmp_path: Path) -> None:
    csv = _write_csv(
        tmp_path / "oneword.csv",
        [
            '"Amazing"',
            '"Absolutely incredible crack pie worth every single calorie"',
        ],
    )
    reviews = ingest(csv)
    assert len(reviews) == 1


@pytest.mark.fast
def test_empty_text_is_dropped(tmp_path: Path) -> None:
    csv = _write_csv(
        tmp_path / "blank.csv",
        [
            '""',
            '"Birthday cake truffles are always incredibly fresh and soft"',
        ],
    )
    reviews = ingest(csv)
    assert len(reviews) == 1


@pytest.mark.fast
def test_emoji_only_is_dropped(tmp_path: Path) -> None:
    csv = _write_csv(
        tmp_path / "emoji.csv",
        [
            '"🎂🎉😍"',
            '"Cereal milk ice cream is rich smooth and totally unique tasting"',
        ],
    )
    reviews = ingest(csv)
    assert len(reviews) == 1


# ---------------------------------------------------------------------------
# Missing / extra columns
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_missing_optional_columns(tmp_path: Path) -> None:
    # Only review_text — no rating, date, review_id
    csv = _write_csv(
        tmp_path / "minimal.csv",
        ['"A wonderful bakery with amazing fresh cookies and soft serve"'],
    )
    reviews = ingest(csv)
    assert len(reviews) == 1
    assert reviews[0]["rating"] is None
    assert reviews[0]["date"] is None
    assert reviews[0]["review_id"] != ""


@pytest.mark.fast
def test_extra_columns_are_ignored(tmp_path: Path) -> None:
    p = tmp_path / "extra.csv"
    p.write_text(
        "review_text,rating,date,source,internal_notes\n"
        '"Cereal milk soft serve is absolutely incredible and worth every penny",5,2024-01-01,yelp,checked\n',
        encoding="utf-8",
    )
    reviews = ingest(p)
    assert len(reviews) == 1
    assert "source" not in reviews[0]
    assert "internal_notes" not in reviews[0]


@pytest.mark.fast
def test_rating_normalised(tmp_path: Path) -> None:
    p = tmp_path / "rating.csv"
    p.write_text(
        "review_text,rating\n"
        '"Crack pie is the best dessert ever made in the world",5\n'
        '"Birthday cake truffles are absolutely incredible and unique","not_a_number"\n'
        '"Cereal milk soft serve is smooth rich and totally delightful","6"\n',  # out of range
        encoding="utf-8",
    )
    reviews = ingest(p)
    assert reviews[0]["rating"] == 5
    assert reviews[1]["rating"] is None    # unparseable → None
    assert reviews[2]["rating"] is None    # out-of-range → None


# ---------------------------------------------------------------------------
# ID assignment and deduplication
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_ids_assigned_when_absent(tmp_path: Path) -> None:
    csv = _write_csv(
        tmp_path / "noids.csv",
        [
            '"Cereal milk soft serve is the ultimate New York treat"',
            '"Birthday cake truffles are dense moist and absolutely addictive"',
        ],
    )
    reviews = ingest(csv)
    assert reviews[0]["review_id"] == "r_001"
    assert reviews[1]["review_id"] == "r_002"


@pytest.mark.fast
def test_user_provided_ids_preserved(tmp_path: Path) -> None:
    p = tmp_path / "ids.csv"
    p.write_text(
        "review_id,review_text\n"
        'custom_99,"Cereal milk soft serve is absolutely the best ice cream ever"\n'
        'custom_77,"Birthday cake truffles are incredibly moist and richly flavored"\n',
        encoding="utf-8",
    )
    reviews = ingest(p)
    assert reviews[0]["review_id"] == "custom_99"
    assert reviews[1]["review_id"] == "custom_77"


@pytest.mark.fast
def test_duplicate_ids_second_occurrence_regenerated(tmp_path: Path) -> None:
    p = tmp_path / "dupids.csv"
    p.write_text(
        "review_id,review_text\n"
        'dup_id,"Cereal milk soft serve is the most unique ice cream flavor ever"\n'
        'unique_id,"Birthday cake truffles are rich moist and absolutely incredible"\n'
        'dup_id,"Crack pie is so sweet buttery and completely unforgettable dessert"\n',
        encoding="utf-8",
    )
    reviews = ingest(p)
    ids = [r["review_id"] for r in reviews]
    assert ids[0] == "dup_id"     # first occurrence preserved
    assert ids[1] == "unique_id"  # unique preserved
    assert ids[2] != "dup_id"     # duplicate occurrence regenerated
    assert len(set(ids)) == 3     # all unique


# ---------------------------------------------------------------------------
# Error conditions
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_missing_file_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        ingest("/nonexistent/path/reviews.csv")


@pytest.mark.fast
def test_empty_csv_raises_value_error(tmp_path: Path) -> None:
    p = _write_csv(tmp_path / "empty.csv", [])  # header only, no data rows
    with pytest.raises(ValueError, match="No reviews found"):
        ingest(p)


@pytest.mark.fast
def test_all_junk_rows_raises_value_error(tmp_path: Path) -> None:
    csv = _write_csv(tmp_path / "alljunk.csv", ['"Hi"', '"Great"', "#ERROR!"])
    with pytest.raises(ValueError, match="No reviews found"):
        ingest(csv)


@pytest.mark.fast
def test_unsupported_extension_raises_value_error(tmp_path: Path) -> None:
    p = tmp_path / "reviews.xlsx"
    p.write_bytes(b"not a real file")
    with pytest.raises(ValueError, match="Unsupported file type"):
        ingest(p)


@pytest.mark.fast
def test_missing_review_text_column_raises(tmp_path: Path) -> None:
    p = tmp_path / "wrongcol.csv"
    p.write_text("body,rating\n\"Great cake\",5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="review_text"):
        ingest(p)


@pytest.mark.fast
def test_invalid_json_raises_value_error(tmp_path: Path) -> None:
    p = tmp_path / "broken.json"
    p.write_text("this is not json at all", encoding="utf-8")
    with pytest.raises(ValueError, match="Cannot parse JSON"):
        ingest(p)


@pytest.mark.fast
def test_json_not_array_raises_value_error(tmp_path: Path) -> None:
    p = tmp_path / "obj.json"
    p.write_text('{"review_text": "A great cake with lots of flavor"}', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON array"):
        ingest(p)


# ---------------------------------------------------------------------------
# JSON happy path
# ---------------------------------------------------------------------------

@pytest.mark.fast
def test_load_json_with_explicit_ids(tmp_path: Path) -> None:
    entries = [
        {"review_id": "j_001", "review_text": "Cereal milk soft serve is absolutely the most unique dessert ever", "rating": 5, "date": "2024-01-01"},
        {"review_id": "j_002", "review_text": "Birthday cake truffles are dense rich moist and incredibly addictive", "rating": 4, "date": "2024-02-01"},
    ]
    p = _write_json(tmp_path / "reviews.json", entries)
    reviews = ingest(p)
    assert len(reviews) == 2
    assert reviews[0]["review_id"] == "j_001"
    assert reviews[0]["rating"] == 5
    assert reviews[1]["review_id"] == "j_002"


@pytest.mark.fast
def test_load_json_without_optional_fields(tmp_path: Path) -> None:
    entries = [
        {"review_text": "Crack pie is buttery sweet rich and absolutely impossible to stop eating"},
    ]
    p = _write_json(tmp_path / "minimal.json", entries)
    reviews = ingest(p)
    assert len(reviews) == 1
    assert reviews[0]["rating"] is None
    assert reviews[0]["date"] is None
    assert reviews[0]["review_id"] != ""
