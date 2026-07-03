"""One JSON line per run. This is the COGS ledger for per-instance pricing."""

import json
import os
from datetime import datetime, timezone


def log(path, **fields):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = {"ts": datetime.now(timezone.utc).isoformat(), **fields}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
