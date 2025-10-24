# Copyright (c) 2024, Bitcoin Depot LLC and contributors
# License: GNU General Public License v3.0. See LICENSE file for details.   
# /home/xg/xg-b/apps/cclms/cclms/api/competitors.py
import requests, time, frappe
from frappe.utils import now_datetime, add_to_date

GOOGLE_PLACES_NEARBY = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

def _zip_centroid(zip_code: str):
    """Return (lat, lng, square_miles) from Zip Code Analytics; None if missing."""
    row = frappe.db.get_value(
        "Zip Code Analytics",
        {"zip_code": zip_code},
        ["latitude", "longitude", "square_miles"],
        as_dict=True,
    )
    if not row or not row.latitude or not row.longitude:
        return None, None, None
    return float(row.latitude), float(row.longitude), (row.square_miles or None)

@frappe.whitelist()
def refresh_competitor_kiosks(zip_code: str, force: int | bool = 0, radius_m: int | None = None):
    """
    Find competitor crypto kiosks near the ZIP centroid (Google Places Nearby).
    - Tries multiple keywords for better recall
    - Reasonable radius (10–25 km) if not provided
    - Upserts by place_id (set DocType autoname = field:place_id)
    Returns: int (inserted/updated count)
    """
    key = frappe.db.get_single_value("Google Maps Settings", "api_key")
    if not key:
        frappe.throw("Google API key missing in Google Maps Settings")

    # Throttle window (24h) unless forced
    if not force:
        since = add_to_date(now_datetime(), hours=-24)
        already = frappe.get_all(
            "Competitor Kiosk",
            filters={"zip_code": zip_code, "modified": [">", since]},
            limit=1,
        )
        if already:
            return 0

    lat, lng, sqmi = _zip_centroid(zip_code)
    if lat is None or lng is None:
        frappe.throw(f"No centroid for ZIP {zip_code}. Import gazetteer centroids first.")

    # Choose a sensible radius if not provided
    if radius_m is None:
        try:
            import math
            if sqmi:
                eq_r_m = math.sqrt(float(sqmi) / math.pi) * 1609.34
                radius_m = int(max(10_000, min(25_000, eq_r_m * 2)))
            else:
                radius_m = 15_000
        except Exception:
            radius_m = 15_000

    keywords = ["bitcoin atm", "crypto atm", "bitcoin kiosk", "crypto kiosk", "bitcoin machine", "cryptocurrency atm"]
    saved = 0
    seen = set()  # place_ids seen this run

    for kw in keywords:
        next_page = None
        for _ in range(3):  # up to ~60 per keyword
            params = {
                "key": key,
                "location": f"{lat},{lng}",
                "radius": radius_m,
                "keyword": kw,
            }
            if next_page:
                params = {"key": key, "pagetoken": next_page}
                time.sleep(2)  # required before using next_page_token

            resp = requests.get(GOOGLE_PLACES_NEARBY, params=params, timeout=15).json()
            results = resp.get("results") or []

            for p in results:
                pid = p.get("place_id")
                if not pid or pid in seen:
                    continue
                seen.add(pid)

                brand = (p.get("name") or "").strip()
                if "bitcoin depot" in brand.lower():
                    continue  # skip our own brand

                loc = (p.get("geometry") or {}).get("location") or {}
                plat, plng = loc.get("lat"), loc.get("lng")
                if plat is None or plng is None:
                    continue

                data = {
                    "place_id": pid,
                    "brand": brand,
                    "zip_code": zip_code,  # anchor ZIP we searched from
                    "latitude": float(plat),
                    "longitude": float(plng),
                    "source": "google_places_nearby",
                }

                existing = frappe.db.exists("Competitor Kiosk", {"place_id": pid})
                if existing:
                    doc = frappe.get_doc("Competitor Kiosk", existing)
                    doc.update(data)
                    doc.save(ignore_permissions=True)
                else:
                    doc = frappe.get_doc({"doctype": "Competitor Kiosk", **data})
                    doc.name = pid  # ensure name == place_id even if autoname not set yet
                    doc.insert(ignore_permissions=True)

                saved += 1

            next_page = resp.get("next_page_token")
            if not next_page:
                break

    frappe.db.commit()
    return saved

@frappe.whitelist()
def refresh_competitors_around_zip(zip_code: str, km: float = 20.0, force: int | bool = 0):
    """
    Sweep all ZIPs whose centroids lie within `km` of the anchor ZIP centroid,
    calling refresh_competitor_kiosks for each. Returns summary dict.
    """
    anchor = frappe.db.get_value(
        "Zip Code Analytics",
        {"zip_code": zip_code},
        ["latitude", "longitude"],
        as_dict=True,
    )
    if not anchor or not anchor.latitude or not anchor.longitude:
        frappe.throw(f"No centroid for ZIP {zip_code}")

    la, lo = float(anchor.latitude), float(anchor.longitude)

    zips = frappe.get_all(
        "Zip Code Analytics",
        fields=["zip_code", "latitude", "longitude"],
        limit_page_length=50000,
    )

    def hav_km(a, b, c, d):
        from math import radians, sin, cos, atan2, sqrt
        R = 6371.0
        dLat = radians(c - a)
        dLon = radians(d - b)
        A = sin(dLat/2)**2 + cos(radians(a)) * cos(radians(c)) * sin(dLon/2)**2
        return 2 * R * atan2(sqrt(A), sqrt(1 - A))

    nearby = [
        r["zip_code"] for r in zips
        if r.get("latitude") and r.get("longitude")
        and hav_km(la, lo, float(r["latitude"]), float(r["longitude"])) <= float(km)
    ]

    total_saved = 0
    for z in nearby:
        # set radius equal to km (converted to meters) for each zip’s local search
        total_saved += int(refresh_competitor_kiosks(z, force=force, radius_m=int(float(km) * 1000)) or 0)

    return {"anchor_zip": zip_code, "zips_scanned": len(nearby), "rows_saved": total_saved}

@frappe.whitelist()
def update_totals_from_company_vs_competitors():
    """
    Optional: if you track our own kiosks in Zip Code Analytics.company_kiosks,
    compute total_kiosks = company_kiosks + competitor_density.
    """
    rows = frappe.get_all(
        "Zip Code Analytics",
        fields=["name","company_kiosks","competitor_density"]
    )
    updated = 0
    for r in rows:
        try:
            ours = int(r.get("company_kiosks") or 0)
            comp = int(r.get("competitor_density") or 0)
            total = ours + comp
            frappe.db.set_value("Zip Code Analytics", r["name"], "total_kiosks", total)
            updated += 1
        except Exception:
            pass
    frappe.db.commit()
    return {"updated": updated}
@frappe.whitelist()
def backfill_kiosk_actual_zip(limit: int = 2000, rate_ms: int = 250):
    """
    Reverse geocode kiosks missing actual_zip_code.
    Fills Competitor Kiosk.actual_zip_code using Google Geocoding (postal_code).
    """
    key = frappe.db.get_single_value("Google Maps Settings", "api_key")
    if not key:
        frappe.throw("Google API key missing in Google Maps Settings")

    rows = frappe.get_all("Competitor Kiosk",
                          fields=["name", "latitude", "longitude"],
                          filters=[["actual_zip_code", "=", ""],
                                   ["latitude", "is", "set"],
                                   ["longitude", "is", "set"]],
                          limit_page_length=limit)

    updated = 0
    for r in rows:
        lat, lng = float(r["latitude"]), float(r["longitude"])
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {"latlng": f"{lat},{lng}", "key": key, "result_type": "postal_code"}
        try:
            j = requests.get(url, params=params, timeout=12).json()
            comps = (j.get("results") or [{}])[0].get("address_components") or []
            zipc = ""
            for c in comps:
                if "postal_code" in c.get("types", []):
                    zipc = (c.get("long_name") or "").strip()
                    break
            if zipc:
                frappe.db.set_value("Competitor Kiosk", r["name"], "actual_zip_code", zipc.zfill(5))
                updated += 1
        except Exception:
            pass
        time.sleep(rate_ms/1000.0)

    frappe.db.commit()
    return {"updated": updated, "scanned": len(rows)}

@frappe.whitelist()
def update_competitor_density(zips: list[str] | None = None):
    """
    Count kiosks per ZIP using actual_zip_code when available, else fallback to zip_code.
    Writes Zip Code Analytics.competitor_density.
    """
    # Build WHERE that accepts either field and ignores blanks
    where = "WHERE COALESCE(NULLIF(actual_zip_code,''), NULLIF(zip_code,'')) IS NOT NULL"
    params = {}

    if zips:
        zlist = tuple(str(z).zfill(5) for z in zips)
        where += " AND COALESCE(NULLIF(actual_zip_code,''), zip_code) IN %(zips)s"
        params["zips"] = zlist

    rows = frappe.db.sql(
        f"""
        SELECT COALESCE(NULLIF(actual_zip_code,''), zip_code) AS zc,
               COUNT(*) AS cnt
        FROM `tabCompetitor Kiosk`
        {where}
        GROUP BY COALESCE(NULLIF(actual_zip_code,''), zip_code)
        """,
        params,
        as_dict=True
    )

    counts = {(r["zc"] or "").zfill(5): int(r["cnt"]) for r in rows}

    updated = 0
    targets = counts.keys() if not zips else [str(z).zfill(5) for z in zips]
    for z in targets:
        name = frappe.db.get_value("Zip Code Analytics", {"zip_code": z}, "name")
        if not name:
            continue
        frappe.db.set_value("Zip Code Analytics", name, "competitor_density", counts.get(z, 0))
        updated += 1

    frappe.db.commit()
    return {"updated": updated, "zips_with_counts": len(counts)}
