"""Census Bureau geocoder. One correct path: no Nominatim, no Google.
Results cached on the ledger record; each permit is geocoded once, ever."""

import time

from curl_cffi import requests

URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"


def geocode_pending(ledger, sleep_s=1.0):
    calls = unmatched = 0
    for pid, rec in ledger.items():
        if rec.get("geocode_status") or not rec.get("address"):
            continue
        r = requests.get(
            URL,
            params={
                "address": f"{rec['address']}, WI",
                "benchmark": "Public_AR_Current",
                "format": "json",
            },
            timeout=30,
        )
        if r.status_code != 200:
            raise ValueError(f"Geocoder HTTP {r.status_code} for {pid}")
        calls += 1
        matches = r.json()["result"]["addressMatches"]
        if matches:
            coords = matches[0]["coordinates"]
            rec["lat"], rec["lon"] = coords["y"], coords["x"]
            rec["geocode_status"] = "matched"
        else:
            rec["lat"] = rec["lon"] = None
            rec["geocode_status"] = "unmatched"
            unmatched += 1
        time.sleep(sleep_s)
    return calls, unmatched
