"""Orchestrator: discover -> download -> parse -> verify -> merge -> geocode
-> build -> telemetry. The ONLY soft exit is 'no new report' (monthly cron
fires before the city publishes). Everything else fails loudly."""

import importlib
import json
import time

from pipeline import build, contract, geocode, ledger, telemetry

LEDGER = "data/ledger.json"
SUMMARIES = "data/summaries.json"
TELEMETRY = "telemetry/runs.jsonl"
OUT = "web/public"


def main():
    t0 = time.time()
    with open("instance.json", encoding="utf-8") as f:
        instance = json.load(f)
    adapter = importlib.import_module(f"pipeline.adapters.{instance['source']}")

    url, as_of, title = adapter.discover_newest()
    try:
        with open(SUMMARIES, encoding="utf-8") as f:
            summaries_by_month = json.load(f)
    except FileNotFoundError:
        summaries_by_month = {}

    if as_of in summaries_by_month:
        telemetry.log(
            TELEMETRY, report_month=as_of, fetch_status="no_new_report",
            duration_s=round(time.time() - t0, 1),
        )
        print(f"No new report (newest is {as_of}, already ingested).")
        return

    pdf_bytes = adapter.download(url)
    records, summaries = adapter.parse(pdf_bytes, url, as_of)

    grand = summaries.pop("_grand_total")
    if len(records) != grand:
        raise ValueError(
            f"Parsed {len(records)} records but report grand total is {grand}"
        )
    for r in records:
        r["verified"] = True
        contract.validate(r)

    led = ledger.load(LEDGER)
    new = ledger.merge(led, records)
    calls, unmatched = geocode.geocode_pending(led)
    ledger.save(led, LEDGER)

    summaries_by_month[as_of] = summaries
    with open(SUMMARIES, "w", encoding="utf-8") as f:
        json.dump(summaries_by_month, f, indent=1, sort_keys=True)

    published = build.build(led, summaries_by_month, instance, OUT)
    telemetry.log(
        TELEMETRY, report_month=as_of, fetch_status="ok", bytes=len(pdf_bytes),
        records_parsed=len(records), grand_total=grand, verified=True,
        new_records=new, geocode_calls=calls, geocode_unmatched=unmatched,
        published=published, duration_s=round(time.time() - t0, 1),
    )
    print(f"{title}: {len(records)}/{grand} verified, {new} new, "
          f"{published} published.")


if __name__ == "__main__":
    main()
