"""
Evaluation script for the review retrievability labeler.

Usage:
    python3 evaluate.py --gold review_retrievability_gold_v3.json \
                        --predictions labeler_outputs.json \
                        --split dev    # or "test"

Computes per-dimension exact agreement, within-1 agreement, bucket agreement,
and breaks down disagreements by gold-confidence level (so you can see whether
the labeler is wrong on easy cases or only on the genuinely ambiguous ones).

Predictions file format: a JSON array of {review_id, labels, relevance, confidence}
objects, where labels has the five dimension scores.
"""
import json
import argparse
from collections import Counter, defaultdict

DIMS = ["service", "attributes", "outcome", "occasion", "descriptive_depth"]
BUCKETS = ["service_attribute_matchable", "trust_quality_matchable", "low_retrievability"]


def bucket_from_labels(labels):
    if labels["service"] >= 2 or labels["attributes"] >= 2:
        return "service_attribute_matchable"
    elif labels["descriptive_depth"] >= 1:
        return "trust_quality_matchable"
    else:
        return "low_retrievability"


def evaluate(gold_data, predictions, split_filter=None):
    # Build gold lookup, optionally filtered by split
    gold_by_id = {}
    for r in gold_data["reviews"]:
        if split_filter and r.get("split") != split_filter:
            continue
        gold_by_id[r["review_id"]] = r

    pred_by_id = {p["review_id"]: p for p in predictions}

    # Coverage check
    missing = set(gold_by_id.keys()) - set(pred_by_id.keys())
    extra = set(pred_by_id.keys()) - set(gold_by_id.keys())
    if missing:
        print(f"WARNING: {len(missing)} gold reviews missing predictions: {sorted(list(missing))[:10]}{'...' if len(missing) > 10 else ''}")
    if extra:
        print(f"WARNING: {len(extra)} predictions for reviews not in gold split.")

    common = set(gold_by_id) & set(pred_by_id)
    if not common:
        print("ERROR: no overlap between gold and predictions.")
        return None

    print(f"\nEvaluating on {len(common)} reviews (split={split_filter or 'all'})\n")

    # Per-dimension agreement
    print("=" * 60)
    print("PER-DIMENSION AGREEMENT")
    print("=" * 60)
    print(f"{'dimension':<20} {'exact':>8} {'within-1':>10}")
    print("-" * 60)
    for dim in DIMS:
        exact = sum(1 for rid in common if gold_by_id[rid]["labels"][dim] == pred_by_id[rid]["labels"][dim])
        within1 = sum(1 for rid in common if abs(gold_by_id[rid]["labels"][dim] - pred_by_id[rid]["labels"][dim]) <= 1)
        n = len(common)
        print(f"{dim:<20} {exact/n*100:>7.1f}% {within1/n*100:>9.1f}%")

    # Bucket agreement (using locked rule applied to BOTH sides)
    print()
    print("=" * 60)
    print("BUCKET AGREEMENT")
    print("=" * 60)
    bucket_match = 0
    confusion = defaultdict(lambda: defaultdict(int))
    for rid in common:
        gold_bucket = gold_by_id[rid]["expected_bucket"]
        pred_bucket = bucket_from_labels(pred_by_id[rid]["labels"])
        if gold_bucket == pred_bucket:
            bucket_match += 1
        confusion[gold_bucket][pred_bucket] += 1
    print(f"Bucket agreement: {bucket_match/len(common)*100:.1f}% ({bucket_match}/{len(common)})")
    print("\nConfusion matrix (rows = gold, cols = predicted):")
    print(f"{'':<35} " + " ".join(f"{b[:14]:>14}" for b in BUCKETS))
    for gold_b in BUCKETS:
        row = f"{gold_b[:33]:<35} "
        for pred_b in BUCKETS:
            row += f"{confusion[gold_b][pred_b]:>14}"
        print(row)

    # Disagreement breakdown by gold confidence
    print()
    print("=" * 60)
    print("DISAGREEMENTS BY GOLD CONFIDENCE")
    print("=" * 60)
    print("(High-confidence disagreements = real labeler errors.")
    print(" Low-confidence disagreements = expected rubric ambiguity.)")
    print()
    by_conf = defaultdict(lambda: {"total": 0, "bucket_disagree": 0})
    for rid in common:
        conf = gold_by_id[rid].get("confidence", "unknown")
        by_conf[conf]["total"] += 1
        gold_bucket = gold_by_id[rid]["expected_bucket"]
        pred_bucket = bucket_from_labels(pred_by_id[rid]["labels"])
        if gold_bucket != pred_bucket:
            by_conf[conf]["bucket_disagree"] += 1
    print(f"{'conf':<10} {'total':>8} {'bucket_disagree':>18} {'rate':>8}")
    for conf in ["high", "medium", "low"]:
        d = by_conf.get(conf, {"total": 0, "bucket_disagree": 0})
        rate = d["bucket_disagree"] / d["total"] * 100 if d["total"] else 0
        print(f"{conf:<10} {d['total']:>8} {d['bucket_disagree']:>18} {rate:>7.1f}%")

    # Relevance agreement
    print()
    print("=" * 60)
    print("RELEVANCE AGREEMENT")
    print("=" * 60)
    rel_match = sum(1 for rid in common if gold_by_id[rid]["relevance"] == pred_by_id[rid].get("relevance", True))
    print(f"Relevance agreement: {rel_match/len(common)*100:.1f}% ({rel_match}/{len(common)})")

    # List worst disagreements (high-confidence bucket flips)
    print()
    print("=" * 60)
    print("HIGH-CONFIDENCE BUCKET DISAGREEMENTS (priority to fix)")
    print("=" * 60)
    high_conf_disagreements = []
    for rid in common:
        if gold_by_id[rid].get("confidence") != "high":
            continue
        gold_bucket = gold_by_id[rid]["expected_bucket"]
        pred_bucket = bucket_from_labels(pred_by_id[rid]["labels"])
        if gold_bucket != pred_bucket:
            high_conf_disagreements.append({
                "rid": rid,
                "text": gold_by_id[rid]["text"][:120],
                "gold_labels": gold_by_id[rid]["labels"],
                "pred_labels": pred_by_id[rid]["labels"],
                "gold_bucket": gold_bucket,
                "pred_bucket": pred_bucket
            })
    if not high_conf_disagreements:
        print("None — labeler agrees on all high-confidence cases.")
    else:
        for d in high_conf_disagreements[:10]:
            print(f"\n{d['rid']}: \"{d['text']}{'...' if len(d['text']) >= 120 else ''}\"")
            print(f"  Gold:  bucket={d['gold_bucket']}, labels={d['gold_labels']}")
            print(f"  Pred:  bucket={d['pred_bucket']}, labels={d['pred_labels']}")
        if len(high_conf_disagreements) > 10:
            print(f"\n... and {len(high_conf_disagreements) - 10} more.")

    print()
    return {
        "n_evaluated": len(common),
        "bucket_agreement": bucket_match / len(common),
        "high_conf_disagreement_count": len([d for d in high_conf_disagreements])
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", required=True, help="Path to gold set JSON")
    parser.add_argument("--predictions", required=True, help="Path to labeler predictions JSON")
    parser.add_argument("--split", choices=["dev", "test", "all"], default="dev",
                        help="Which split to evaluate on (default: dev)")
    args = parser.parse_args()

    with open(args.gold) as f:
        gold = json.load(f)
    with open(args.predictions) as f:
        preds = json.load(f)
    if isinstance(preds, dict) and "predictions" in preds:
        preds = preds["predictions"]

    split_filter = None if args.split == "all" else args.split
    evaluate(gold, preds, split_filter=split_filter)
