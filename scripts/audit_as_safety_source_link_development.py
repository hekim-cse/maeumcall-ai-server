"""Audit a rejected source-link rule on exposed, gold-span A/S cases only.

This is a gold-span development diagnostic of one conservative rule, not a
performance ceiling. Neither spans nor relation labels are available to the
live service, and the fresh GB holdout is never loaded.
"""

from __future__ import annotations

import json
from collections import Counter

from scripts.probe_as_safety_source_link_v1 import link_source
from scripts.run_as_safety_gold_owner_link_diagnostic import SOURCE_PATHS, load_gold_owner_cases


def audit() -> dict:
    """Count relation decisions against previously reviewed RE/V cases."""
    selected = load_gold_owner_cases(
        SOURCE_PATHS["spans_sha256"], SOURCE_PATHS["owner_labels_sha256"]
    )
    counts: Counter[tuple[str, str]] = Counter()
    observed_current = 0
    observed_current_direct = 0
    for case, span, owner in selected:
        gold = case["expected_relation"]
        relation = span.get("reviewed_interpretation", {}).get(
            "target_relation", gold["target_relation"]
        )
        predicted = link_source(
            case["user_message"],
            target_mention=span["target_mention"],
            target_clause_index=gold["product_index"],
            owner_mention=owner["mention"],
            owner_clause_index=owner["clause_index"],
        )["source_relation"]
        counts[(relation, predicted)] += 1
        if relation == "current" and gold["event_status"] == "observed":
            observed_current += 1
            observed_current_direct += predicted == "current"
    return {
        "claim_scope": "already_exposed_ai_authored_gold_span_development_only",
        "denominator": len(selected),
        "gold_current": sum(count for (gold, _), count in counts.items() if gold == "current"),
        "gold_other": sum(count for (gold, _), count in counts.items() if gold == "other"),
        "current_correct": counts[("current", "current")],
        "other_correct": counts[("other", "other")],
        "abstentions": sum(
            count for (_, predicted), count in counts.items() if predicted == "unknown"
        ),
        "observed_current": observed_current,
        "observed_current_direct": observed_current_direct,
        "confusion": {
            f"{gold}->{predicted}": count for (gold, predicted), count in sorted(counts.items())
        },
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
