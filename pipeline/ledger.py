"""Idempotent ledger keyed on source_permit_id. Append-only; re-running a
month is a no-op; a CHANGED record for an existing id raises (the monthly
report is a snapshot -- silent mutation means something is wrong)."""

import json
import os

GEOCODE_FIELDS = {"lat", "lon", "geocode_status"}


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def merge(ledger, records):
    new = 0
    for r in records:
        pid = r["source_permit_id"]
        if pid in ledger:
            existing = {
                k: v for k, v in ledger[pid].items() if k not in GEOCODE_FIELDS
            }
            if existing != r:
                raise ValueError(
                    f"Ledger conflict: source record {pid} changed between runs"
                )
        else:
            ledger[pid] = dict(r)
            new += 1
    return new

def save(ledger, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=1, sort_keys=True)
    os.replace(tmp, path)
