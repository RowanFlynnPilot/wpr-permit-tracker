"""Acceptance tests per RESHAPE.md. Run: python tests/acceptance.py
Parses both fixture months; any failure raises."""

import re
import sys

sys.path.insert(0, ".")
from pipeline import contract
from pipeline.adapters import wausau_monthly_pdf as adapter


def run_month(path, as_of):
    with open(path, "rb") as f:
        records, summaries = adapter.parse(f.read(), path, as_of)
    grand = summaries.pop("_grand_total")
    assert len(records) == grand, f"{as_of}: parsed {len(records)} != grand {grand}"
    for r in records:
        r["verified"] = True
        contract.validate(r)
    stuck = [r for r in records if re.search(r"\d{12,}", r.get("address") or "")]
    assert not stuck, f"{as_of}: parcel IDs stuck in address: {len(stuck)}"
    print(f"  {as_of}: {len(records)}/{grand} verified | "
          f"jurisdictions: {sorted(set(r['jurisdiction'] for r in records))}")
    return records


print("== May 2026 ==")
may = run_month("tests/fixtures/wausau_may2026.pdf", "2026-05")

chamber = [r for r in may if r["source_permit_id"] == "202604752"][0]
assert chamber["contractor"] == "GREATER WAUSAU CHAMBER OF COMMERCE", chamber
assert chamber["owner"] == "WI PUBLIC SERVICE CORP ATTN: TAX DEPARTMENT", chamber
assert chamber["description"] == "Egress Exit and deck", chamber
print("  contractor-wrap fix verified on Chamber of Commerce record")

frag = [r for r in may
        if re.search(r"\b(LLC|INC|CORP|COMPANY|COMMERCE)\.?$", r["description"])]
assert not frag, f"descriptions ending in org fragments: {[r['source_permit_id'] for r in frag]}"
print("  no descriptions end with org-name fragments")

print("== April 2026 (format-stability check) ==")
run_month("tests/fixtures/wausau_apr2026.pdf", "2026-04")

print("ALL ACCEPTANCE CHECKS PASSED")
