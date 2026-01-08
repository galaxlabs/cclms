import frappe
from frappe.utils import now_datetime
from cclms.services.zipintel.rules import classify_zip_row, get_criteria

LOCK_KEY = "zipintel_refresh_lock"

def _next_batch_zip_codes(batch_size: int, last_cursor: str):
    last_cursor = (last_cursor or "").zfill(5) if last_cursor else ""
    cond = ""
    vals = []
    if last_cursor:
        cond = "and zip_code > %s"
        vals.append(last_cursor)

    rows = frappe.db.sql(
        f"""
        select zip_code
        from `tabZip Code Analytics`
        where zip_code is not null and zip_code != ''
        {cond}
        order by zip_code asc
        limit %s
        """,
        vals + [int(batch_size)],
        as_dict=True
    )
    zips = [r["zip_code"].zfill(5) for r in rows]
    if zips:
        return zips, zips[-1]

    # wrap-around
    rows = frappe.db.sql(
        """
        select zip_code
        from `tabZip Code Analytics`
        where zip_code is not null and zip_code != ''
        order by zip_code asc
        limit %s
        """,
        [int(batch_size)],
        as_dict=True
    )
    zips = [r["zip_code"].zfill(5) for r in rows]
    return zips, (zips[-1] if zips else "")

def _count_competitor_kiosks(zip_list):
    if not zip_list:
        return {}
    rows = frappe.db.sql(
        """
        select zip_code, count(*) as cnt
        from `tabCompetitor Kiosk`
        where zip_code in %(zips)s
        group by zip_code
        """,
        {"zips": tuple(zip_list)},
        as_dict=True
    )
    return {r["zip_code"].zfill(5): int(r["cnt"]) for r in rows}

def _count_company_kiosks(zip_list):
    """
    Decide what 'company_kiosks' means.
    Easiest: count ATM Leads by ZIP (or only certain statuses).
    """
    if not zip_list:
        return {}

    criteria = get_criteria()
    statuses_raw = (getattr(criteria, "lead_statuses_to_count", "") or "").strip()
    statuses = [s.strip() for s in statuses_raw.split(",") if s.strip()]

    if statuses:
        rows = frappe.db.sql(
            """
            select zippostal_code as zip_code, count(*) as cnt
            from `tabATM Leads`
            where zippostal_code in %(zips)s
              and status in %(statuses)s
            group by zippostal_code
            """,
            {"zips": tuple(zip_list), "statuses": tuple(statuses)},
            as_dict=True
        )
    else:
        # default: count all leads with a ZIP
        rows = frappe.db.sql(
            """
            select zippostal_code as zip_code, count(*) as cnt
            from `tabATM Leads`
            where zippostal_code in %(zips)s
            group by zippostal_code
            """,
            {"zips": tuple(zip_list)},
            as_dict=True
        )

    return {str(r["zip_code"]).zfill(5): int(r["cnt"]) for r in rows}

def refresh_zip_analytics_batch():
    criteria = get_criteria()
    if not int(criteria.enabled or 0):
        return {"ok": False, "msg": "ATM Criteria disabled"}

    batch_size = int(criteria.batch_size or 100)

    cache = frappe.cache()
    lock = cache.lock(LOCK_KEY, timeout=600)
    if not lock.acquire(blocking=False):
        return {"ok": False, "msg": "Already running"}

    try:
        last_cursor = getattr(criteria, "last_zip_cursor", "") or ""
        zip_list, new_cursor = _next_batch_zip_codes(batch_size, last_cursor)

        comp_counts = _count_competitor_kiosks(zip_list)
        company_counts = _count_company_kiosks(zip_list)

        updated = 0
        for z in zip_list:
            row = frappe.db.get_value("Zip Code Analytics", {"zip_code": z}, "*", as_dict=True)
            if not row:
                continue

            competitor = comp_counts.get(z, 0)
            company = company_counts.get(z, 0)
            total = competitor + company  # your intended meaning

            row["competitor_kiosks"] = competitor
            row["company_kiosks"] = company
            row["total_kiosks"] = total

            zone, matched_rule, _debug = classify_zip_row(row)

            frappe.db.set_value("Zip Code Analytics", row["name"], {
                "competitor_kiosks": competitor,
                "company_kiosks": company,
                "total_kiosks": total,
                "zone_color": zone,
                "matched_rule": matched_rule,
                "zone_updated_on": now_datetime(),
            })
            updated += 1

        criteria.last_zip_cursor = new_cursor
        criteria.save(ignore_permissions=True)

        frappe.db.commit()
        return {"ok": True, "updated": updated, "cursor": new_cursor}
    finally:
        lock.release()
