# wpr-permit-tracker

Monthly building-permit tracker for Wausau Pilot & Review. Parses the City
of Wausau "Monthly - Permits Issued" PDF (covers Wausau, Schofield, and Rib
Mountain), maintains an append-only ledger, geocodes via the Census Bureau,
applies editorial policy, and publishes a Leaflet map widget to GitHub Pages
for WordPress iframe embedding.

Pipeline validated against real data: May 2026 (838/838 records) and
April 2026 (631/631). See RESHAPE.md for architecture and CLAUDE.md for
conventions.

Run: `python -m pip install -r requirements.txt; python tests/acceptance.py; python -m pipeline.run`
