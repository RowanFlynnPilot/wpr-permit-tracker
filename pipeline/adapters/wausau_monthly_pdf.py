"""Adapter: City of Wausau 'Monthly - Permits Issued' PDF (Evolve permit system).

Owns everything source-specific: report discovery, download (Akamai requires
curl_cffi Chrome impersonation), and positional PDF parsing. Emits canonical
record dicts conforming to pipeline.contract.PermitRecord plus per-jurisdiction
summaries. Every constant below was measured against the May 2026 report
(838/838 records validated). See RESHAPE.md for the evidence trail.
"""

import io
import re
from datetime import datetime

import pdfplumber
from curl_cffi import requests

SOURCE = "wausau_monthly_pdf"
ACTIVITY_URL = (
    "https://www.wausauwi.gov/your-government/inspections/"
    "permit-information/building-permit-activity"
)
BASE = "https://www.wausauwi.gov"

# Measured column boundaries (x0 ranges, points). Parcel tokens start at
# exactly x0=314; the 313 boundary is correct, 316 was tried and is wrong.
COLS = [
    ("permit_id", 25, 100),
    ("template", 100, 190),
    ("address", 190, 313),
    ("parcel_id", 313, 400),
    ("owner", 400, 520),
    ("contractor", 520, 635),
    ("issue_date", 635, 710),
    ("last_insp", 710, 792),
]

# Post-sqft-line wrap disambiguation (measured):
#   description data always starts at x0=459 (label 'Description' sits at 405)
#   owner wraps start ~404, contractor wraps start ~524; mixed lines exist.
DESC_X = 455  # first-word x0 >= this and < CONTRACTOR_X0 -> description line
OWNER_X0 = 400
CONTRACTOR_X0 = 520

PERMIT_ID_RE = re.compile(r"20\d{7}")
NUM_RE = re.compile(r"[\d,]+")
LINE_TOL = 3  # points; cluster by proximity, NEVER round(top) (splits lines)


def _col_for(x0):
    for name, lo, hi in COLS:
        if lo <= x0 < hi:
            return name
    return None


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def _iso(date_str):
    return datetime.strptime(date_str.strip(), "%m/%d/%Y").strftime("%Y-%m-%d")


def _cluster_lines(words, tol=LINE_TOL):
    lines = []
    for w in sorted(words, key=lambda w: w["top"]):
        if lines and w["top"] - lines[-1][0]["top"] <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def discover_newest():
    """Return (url, as_of, title) for the newest monthly report.

    Scrapes the activity page for the highest-year folder, then that folder
    for document links titled 'Building Activity_{Month} {Year}'.
    """
    page = _get(ACTIVITY_URL).text
    folders = re.findall(
        r'href="([^"]*-folder-\d+)"[^>]*>\s*(\d{4}) Building Activity', page
    )
    if not folders:
        raise ValueError("No year folders found on activity page; layout changed")
    href, _year = max(folders, key=lambda f: int(f[1]))
    folder = _get(BASE + href).text
    docs = re.findall(
        r'href="(/home/showpublisheddocument/\d+/\d+)"[^>]*>\s*'
        r"Building Activity_(\w+) (\d{4})",
        folder,
    )
    if not docs:
        raise ValueError("No report documents found in year folder; layout changed")
    dated = [
        (datetime.strptime(f"{month} {year}", "%B %Y"), path, f"{month} {year}")
        for path, month, year in docs
    ]
    dt, path, title = max(dated)
    return BASE + path, dt.strftime("%Y-%m"), title


def download(url):
    r = _get(url)
    ctype = r.headers.get("content-type", "")
    if not ctype.startswith("application/pdf"):
        raise ValueError(f"Expected application/pdf, got {ctype!r} from {url}")
    return r.content


def _get(url):
    r = requests.get(url, impersonate="chrome", timeout=60)
    if r.status_code != 200:
        raise ValueError(f"HTTP {r.status_code} fetching {url}")
    return r


def _parse_sqft_line(ws, cur):
    """Positionally parse the 'Finished Sq Ft ... Description ...' line.

    Bold words are template labels; numeric regular words in the windows
    bounded by the labels are the values; non-numeric regular words are
    wrapped column text (measured in April 2026: owner wraps can share
    this visual line) routed by column, except x0 >= DESC_X which is
    description text. Known ambiguity: a contractor wrap sharing this exact
    line is indistinguishable from description flow; not observed in
    Apr/May 2026 data.
    """
    labels = {}
    for w in ws:
        if "Bold" in w["fontname"]:
            labels.setdefault(w["text"], []).append(w)
    for req in ("Finished", "Unfinished", "Units", "Description"):
        if req not in labels:
            raise ValueError(
                f"sqft line missing label {req!r} (layout drift?): "
                f"{' '.join(w['text'] for w in ws)!r}"
            )
    win = {
        "finished_sqft": (labels["Finished"][0]["x1"], labels["Unfinished"][0]["x0"]),
        "unfinished_sqft": (labels["Unfinished"][0]["x1"], labels["Units"][0]["x0"]),
        "units": (labels["Units"][0]["x1"], labels["Description"][0]["x0"]),
    }
    cur.setdefault("finished_sqft", None)
    cur.setdefault("unfinished_sqft", None)
    cur.setdefault("units", None)
    desc_words = []
    for w in ws:
        if "Bold" in w["fontname"]:
            continue
        x0, text = w["x0"], w["text"]
        numeric = bool(NUM_RE.fullmatch(text))
        placed = False
        if numeric:
            for field, (lo, hi) in win.items():
                if lo <= x0 < hi:
                    cur[field] = int(text.replace(",", ""))
                    placed = True
                    break
        if placed:
            continue
        if x0 >= DESC_X:
            desc_words.append(text)
        else:
            col = _col_for(x0)
            if col is None:
                raise ValueError(
                    f"Unclassifiable word on sqft line at x0={x0:.0f}: {text!r}"
                )
            cur[col] = (cur.get(col, "") + " " + text).strip()
    cur["description"] = " ".join(desc_words)


def parse(pdf_bytes, source_document, as_of):
    """Parse report PDF -> (records, summaries).

    records: list of dicts conforming to PermitRecord (verified set by caller
             after the grand-total check in pipeline.run).
    summaries: {jurisdiction_slug: {"permits_issued": int, "valuation": int}}
               plus {"_grand_total": int} taken from the report's final count.
    """
    records, summaries = [], {}
    jurisdiction = "unassigned"
    cur = None
    in_desc = False
    last_count_line = None

    def flush():
        nonlocal cur, in_desc
        if cur is not None:
            records.append(cur)
        cur, in_desc = None, False

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(extra_attrs=["size", "fontname"])
            for ws in _cluster_lines(words):
                texts = [w["text"] for w in ws]
                joined = " ".join(texts)

                # Jurisdiction header: whole line Arial Bold 10.5
                if all("Bold" in w["fontname"] and 10 < w["size"] < 11 for w in ws):
                    flush()
                    jurisdiction = _slug(joined)
                    continue

                m = re.search(r"Permits Issued\s+([\d,]+)", joined)
                if m and "Sq" not in joined:
                    flush()
                    count = int(m.group(1).replace(",", ""))
                    summaries.setdefault(jurisdiction, {})["permits_issued"] = count
                    last_count_line = count
                    continue

                if joined == "Valuation":
                    # Bare label opening a section summary block; section over.
                    flush()
                    continue

                m = re.search(r"Valuation\s+\$([\d,]+)", joined)
                if m:
                    summaries.setdefault(jurisdiction, {})["valuation"] = int(
                        m.group(1).replace(",", "")
                    )
                    continue

                if joined.startswith(
                    ("Permit # Templates", "Permit_Unit", "Monthly - Permits")
                ):
                    continue

                if "Finished Sq Ft" in joined:
                    if cur is None:
                        continue
                    _parse_sqft_line(ws, cur)
                    in_desc = True
                    continue

                # New record: 9-digit permit id in the permit_id column
                if (
                    PERMIT_ID_RE.fullmatch(texts[0])
                    and _col_for(ws[0]["x0"]) == "permit_id"
                ):
                    flush()
                    cur = {"jurisdiction": jurisdiction}
                    for w in ws:
                        col = _col_for(w["x0"])
                        if col:
                            cur[col] = (cur.get(col, "") + " " + w["text"]).strip()
                    continue

                if cur is None:
                    continue

                if not in_desc:
                    # Record-header wrap: plain column assignment
                    for w in ws:
                        col = _col_for(w["x0"])
                        if col:
                            cur[col] = (cur.get(col, "") + " " + w["text"]).strip()
                    continue

                # Post-sqft wrap disambiguation (measured rule)
                first_x = ws[0]["x0"]
                if first_x >= DESC_X and first_x < CONTRACTOR_X0 + 120:
                    if first_x < CONTRACTOR_X0:
                        cur["description"] = (
                            cur["description"] + " " + joined
                        ).strip()
                    else:
                        cur["contractor"] = (
                            cur.get("contractor", "") + " " + joined
                        ).strip()
                elif OWNER_X0 <= first_x < DESC_X:
                    for w in ws:
                        field = (
                            "contractor" if w["x0"] >= CONTRACTOR_X0 else "owner"
                        )
                        cur[field] = (cur.get(field, "") + " " + w["text"]).strip()
                else:
                    raise ValueError(
                        f"Unclassifiable post-description wrap at x0={first_x:.0f}: "
                        f"{joined!r}"
                    )
        flush()

    # The report's final 'Permits Issued' line is the grand total
    # (verified May 2026: 2 + 5 + 11 + 820 = 838).
    if last_count_line is None:
        raise ValueError("No 'Permits Issued' summary lines found; layout changed")
    summaries["_grand_total"] = last_count_line

    out = []
    for r in records:
        issue = r.get("issue_date")
        if not issue:
            raise ValueError(f"Record {r.get('permit_id')} missing issue_date")
        out.append(
            {
                "source_permit_id": r["permit_id"],
                "jurisdiction": r["jurisdiction"],
                "template": r.get("template", ""),
                "address": r.get("address") or None,
                "parcel_id": r.get("parcel_id") or None,
                "owner": r.get("owner") or None,
                "contractor": r.get("contractor") or None,
                "issue_date": _iso(issue),
                "last_insp": _iso(r["last_insp"]) if r.get("last_insp") else None,
                "finished_sqft": r.get("finished_sqft"),
                "unfinished_sqft": r.get("unfinished_sqft"),
                "units": r.get("units"),
                "description": r.get("description", ""),
                "source": SOURCE,
                "source_document": source_document,
                "as_of": as_of,
                "verified": False,  # set by pipeline.run after grand-total check
            }
        )
    return out, summaries
