"""
Comprehensive validator for the gold set fixture.
Checks structure, completeness, consistency, and rule compliance.
Reports issues; does not modify the file.
"""
import json
import sys
import pathlib
from collections import Counter, defaultdict

PATH = pathlib.Path(__file__).parent.parent / "tests" / "fixtures" / "review_retrievability_gold_v3.json"

# Expected schema
REQUIRED_REVIEW_FIELDS = {
    "review_id", "source", "business", "rating", "word_count", "text",
    "labels", "relevance", "confidence", "expected_bucket", "labeler_notes"
}
REQUIRED_LABEL_FIELDS = {"service", "attributes", "outcome", "occasion", "descriptive_depth"}
VALID_DIM_SCORES = {0, 1, 2}
VALID_BUCKETS = {"service_attribute_matchable", "trust_quality_matchable", "low_retrievability"}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_SOURCES = {"yelp", "user_contributed_LLM_generated"}

def bucket_from_rule(labels):
    """Apply the locked classification rule."""
    if labels["service"] >= 2 or labels["attributes"] >= 2:
        return "service_attribute_matchable"
    elif labels["descriptive_depth"] >= 1:
        return "trust_quality_matchable"
    else:
        return "low_retrievability"

def validate(data):
    issues = defaultdict(list)
    
    # 1. Top-level structure
    required_top = {"fixture_metadata", "rubric", "reviews", "corpus_summary"}
    missing_top = required_top - set(data.keys())
    if missing_top:
        issues["structure"].append(f"Missing top-level keys: {missing_top}")
    
    reviews = data.get("reviews", [])
    if not reviews:
        issues["structure"].append("No reviews in fixture")
        return issues
    
    # 2. Per-review validation
    seen_ids = set()
    for i, r in enumerate(reviews):
        rid = r.get("review_id", f"<index_{i}>")
        
        # Required fields
        missing = REQUIRED_REVIEW_FIELDS - set(r.keys())
        if missing:
            issues["missing_fields"].append(f"{rid}: missing {missing}")
            continue
        
        # Unique IDs
        if rid in seen_ids:
            issues["duplicate_ids"].append(rid)
        seen_ids.add(rid)
        
        # Source enum
        if r["source"] not in VALID_SOURCES:
            issues["invalid_source"].append(f"{rid}: source='{r['source']}'")
        
        # Confidence enum
        if r["confidence"] not in VALID_CONFIDENCE:
            issues["invalid_confidence"].append(f"{rid}: confidence='{r['confidence']}'")
        
        # Bucket enum
        if r["expected_bucket"] not in VALID_BUCKETS:
            issues["invalid_bucket"].append(f"{rid}: bucket='{r['expected_bucket']}'")
        
        # Labels: all dims present, all values 0/1/2
        labels = r.get("labels", {})
        missing_dims = REQUIRED_LABEL_FIELDS - set(labels.keys())
        if missing_dims:
            issues["missing_dimensions"].append(f"{rid}: missing {missing_dims}")
        for dim in REQUIRED_LABEL_FIELDS:
            if dim in labels:
                v = labels[dim]
                if v not in VALID_DIM_SCORES:
                    issues["invalid_dim_score"].append(f"{rid}.{dim}={v} (must be 0/1/2)")
        
        # Bucket consistency with locked rule
        if all(d in labels for d in REQUIRED_LABEL_FIELDS):
            try:
                expected = bucket_from_rule(labels)
                if expected != r["expected_bucket"]:
                    issues["rule_violations"].append(
                        f"{rid}: rule says '{expected}', fixture says '{r['expected_bucket']}', labels={labels}"
                    )
            except (TypeError, KeyError):
                issues["rule_check_failed"].append(f"{rid}: could not apply rule")
        
        # Word count sanity
        text = r.get("text", "")
        if isinstance(text, str):
            actual_wc = len(text.split())
            claimed_wc = r.get("word_count", -1)
            # Allow some tolerance for hyphens/punctuation
            if abs(actual_wc - claimed_wc) > 3:
                issues["word_count_mismatch"].append(
                    f"{rid}: claimed={claimed_wc}, actual={actual_wc}"
                )
        
        # Empty text
        if not text or not text.strip():
            issues["empty_text"].append(rid)
        
        # Confidence sanity for thin reviews
        # Refined: high-confidence is OK on a short review IF the labels are
        # all-zero (clearly generic) OR include a specific (service≥2 or attributes≥2).
        # The flag fires on the in-between case where short text has weak partial
        # signals (service=1 or attributes=1, depth=0/1) — those are actually hard
        # to label confidently.
        wc = r.get("word_count", 0)
        if wc <= 5 and r.get("confidence") == "high":
            all_zero = all(labels.get(d, 0) == 0 for d in REQUIRED_LABEL_FIELDS)
            has_specific = labels.get("service", 0) >= 2 or labels.get("attributes", 0) >= 2
            if not (all_zero or has_specific):
                issues["suspicious_high_confidence"].append(
                    f"{rid}: ≤5 words, high confidence, but partial signal (service={labels.get('service')}, attributes={labels.get('attributes')}, depth={labels.get('descriptive_depth')})"
                )
        
        # Relevance and bucket consistency
        # If relevance=false, bucket should be low_retrievability
        if r.get("relevance") is False and r.get("expected_bucket") != "low_retrievability":
            issues["irrelevant_not_low"].append(
                f"{rid}: relevance=false but bucket={r['expected_bucket']}"
            )
        
        # User-contributed reviews shouldn't have ratings (they're not real Yelp)
        if r.get("source") == "user_contributed_LLM_generated" and r.get("rating") is not None:
            issues["user_review_has_rating"].append(rid)
    
    # 3. Corpus summary consistency check
    cs = data.get("corpus_summary", {})
    declared_total = cs.get("total_reviews")
    actual_total = len(reviews)
    if declared_total != actual_total:
        issues["summary_mismatch"].append(
            f"corpus_summary.total_reviews={declared_total}, actual={actual_total}"
        )
    
    # Recompute and compare buckets
    actual_buckets = Counter(r["expected_bucket"] for r in reviews)
    declared_buckets = cs.get("by_bucket_overall", {})
    for b in VALID_BUCKETS:
        if actual_buckets[b] != declared_buckets.get(b, 0):
            issues["summary_mismatch"].append(
                f"by_bucket_overall.{b}: declared={declared_buckets.get(b, 0)}, actual={actual_buckets[b]}"
            )
    
    return issues

def report(issues):
    if not issues:
        print("✓ ALL CHECKS PASSED")
        return True
    
    print(f"Found {sum(len(v) for v in issues.values())} issues across {len(issues)} categories:\n")
    for category, items in sorted(issues.items()):
        print(f"## {category} ({len(items)})")
        for item in items[:30]:
            print(f"  - {item}")
        if len(items) > 30:
            print(f"  ... and {len(items) - 30} more")
        print()
    return False

if __name__ == "__main__":
    with open(PATH) as f:
        data = json.load(f)
    issues = validate(data)
    ok = report(issues)
    sys.exit(0 if ok else 1)
