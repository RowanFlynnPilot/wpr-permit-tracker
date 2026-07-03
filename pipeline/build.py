"""Ledger -> web/public JSON. The web app reads these plus instance.json."""

import json
import os
from collections import Counter

from pipeline import policy


def build(ledger, summaries_by_month, instance, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    published, agg = policy.apply(
        ledger, instance["policy"], set(instance["jurisdictions"])
    )
    published.sort(key=lambda r: (r["as_of"], r["issue_date"]), reverse=True)

    contractors = Counter(
        r["contractor"] for r in ledger.values() if r.get("contractor")
    )
    summary = {
        "months": summaries_by_month,
        "aggregate_streets": agg,
        "top_contractors": contractors.most_common(50),
    }
    with open(os.path.join(out_dir, "instance.json"), "w", encoding="utf-8") as f:
        json.dump(instance, f, indent=1)
    with open(os.path.join(out_dir, "permits.json"), "w", encoding="utf-8") as f:
        json.dump(published, f, indent=1)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    return len(published)
