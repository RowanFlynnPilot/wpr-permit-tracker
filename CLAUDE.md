# wpr-permit-tracker — conventions

Read RESHAPE.md first. All parser constants in the adapter were MEASURED
against real May/April 2026 reports (838/838 and 631/631 validated). Do not
re-derive or "clean up" boundaries.

## Environment
- Windows PowerShell 5.1, semicolon chaining. `python -m pip`.
- Project: C:\Users\rpfly\Projects\wpr-permit-tracker. Org: RowanFlynnPilot.

## Principles
- One correct path. No fallbacks. Fail loud on any layout drift.
- Surgical changes only. Evidence before parsing (measure x-coords first).
- Ledger is append-only; a changed record for an existing permit id RAISES.
- The ONLY soft exit is `no_new_report` in pipeline/run.py.

## GitHub Pages (from wpr-finance-tools, do not relearn this)
The Pages site is created ONCE, manually:
  gh api repos/RowanFlynnPilot/wpr-permit-tracker/pages -X POST -f build_type=workflow
NEVER add `enablement: true` to the workflow. The workflow only deploys.

## Fetching wausauwi.gov
Akamai fronts the site. Plain requests 403. curl_cffi with
impersonate="chrome" works from datacenter IPs (verified 2026-07-02). If
Actions IPs get blocked, telemetry/runs.jsonl will show it; the fix at that
point is Webshare residential proxies (wpr-obituaries pattern). Do NOT
pre-build proxy support.

## Commands
- Acceptance: python tests/acceptance.py   (must pass before any commit)
- Full run:   python -m pipeline.run
- Web dev:    cd web; npm install; npm run dev

## Multi-tenant discipline (Gavel lessons)
All jurisdiction, branding, sponsor knowledge lives in instance.json.
Grep check: "wausau" may appear ONLY in the adapter (filename + internals),
instance.json, fixtures, and docs. Never in web/ or the generic pipeline
modules.
