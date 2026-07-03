"""PermitRecord contract. Records either conform or the run fails."""

import re

REQUIRED = {
    "source_permit_id", "jurisdiction", "template", "address", "parcel_id",
    "owner", "contractor", "issue_date", "last_insp", "finished_sqft",
    "unfinished_sqft", "units", "description", "source", "source_document",
    "as_of", "verified",
}

_PERMIT = re.compile(r"20\d{7}")
_PARCEL = re.compile(r"\d{12,15}")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_MONTH = re.compile(r"\d{4}-\d{2}")


def validate(r):
    missing = REQUIRED - set(r)
    if missing:
        raise ValueError(f"Record missing fields {sorted(missing)}: {r}")
    if not _PERMIT.fullmatch(r["source_permit_id"]):
        raise ValueError(f"Bad permit id: {r['source_permit_id']!r}")
    if r["parcel_id"] is not None and not _PARCEL.fullmatch(r["parcel_id"]):
        raise ValueError(
            f"Bad parcel_id {r['parcel_id']!r} on {r['source_permit_id']}"
        )
    if not _DATE.fullmatch(r["issue_date"]):
        raise ValueError(
            f"Bad issue_date {r['issue_date']!r} on {r['source_permit_id']}"
        )
    if r["last_insp"] is not None and not _DATE.fullmatch(r["last_insp"]):
        raise ValueError(
            f"Bad last_insp {r['last_insp']!r} on {r['source_permit_id']}"
        )
    if not _MONTH.fullmatch(r["as_of"]):
        raise ValueError(f"Bad as_of {r['as_of']!r}")
