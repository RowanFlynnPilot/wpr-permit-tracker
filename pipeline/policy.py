"""Editorial rules. Thresholds and template classes live in instance.json;
this module only enforces them. Suppression removes fields from the PUBLIC
output -- the ledger keeps everything."""

import re

ORG_TOKENS = {
    "LLC", "INC", "CORP", "CO", "COMPANY", "TRUST", "CHURCH", "CITY",
    "VILLAGE", "COUNTY", "SCHOOL", "DISTRICT", "STATE", "LLP", "LTD",
    "ASSOCIATION", "ASSOC", "PARTNERS", "PROPERTIES", "HOLDINGS", "GROUP",
    "FOUNDATION", "MINISTRIES", "AUTHORITY", "DEPARTMENT", "SERVICE",
    "SEWERAGE", "CHAMBER", "BANK", "CREDIT", "UNION",
}


def _is_org(name):
    return bool(name) and bool(set(re.split(r"[^A-Z]+", name.upper())) & ORG_TOKENS)


def _street(address):
    return re.sub(r"^\S+\s+", "", address.split(",")[0]).strip()


def apply(ledger, policy_cfg, jurisdictions):
    """-> (publishable_records, aggregate_street_counts)"""
    aggregate = set(policy_cfg["aggregate_templates"])
    feature = set(policy_cfg["feature_templates"])
    published, streets = [], {}
    for rec in ledger.values():
        if rec["jurisdiction"] not in jurisdictions:
            continue
        if not rec["address"]:
            continue  # unmappable; includes Evolve's null-jurisdiction group
        if rec["template"] in aggregate:
            key = (rec["jurisdiction"], _street(rec["address"]))
            streets[key] = streets.get(key, 0) + 1
            continue
        out = dict(rec)
        out["layer"] = "feature" if rec["template"] in feature else "standard"
        if out["layer"] == "standard" and not _is_org(out.get("owner")):
            out.pop("owner", None)
        published.append(out)
    agg = [
        {"jurisdiction": j, "street": s, "count": n}
        for (j, s), n in sorted(streets.items(), key=lambda kv: -kv[1])
    ]
    return published, agg
