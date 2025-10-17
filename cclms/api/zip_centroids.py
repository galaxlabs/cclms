# /home/xg/xg-b/apps/cclms/cclms/api/zip_centroids.py

import requests
import csv
import frappe

@frappe.whitelist()
def import_zcta_centroids(path: str):
    """
    Upsert ZIP (ZCTA) rows into Zip Code Analytics from Census Gazetteer (2020–2025).
    File is typically '|' delimited. Expected columns:
      GEOID, INTPTLAT, INTPTLONG, ALAND_SQMI, AWATER_SQMI
    For each ZIP (GEOID):
      - create doc if missing (zip_code)
      - set centroid_latitude / centroid_longitude
      - set square_miles = ALAND_SQMI + AWATER_SQMI when available
    """
    dt = "Zip Code Analytics"
    if not frappe.db.table_exists(dt):
        frappe.throw("Zip Code Analytics doctype not found")

    # Build an index of existing zip -> name
    existing = frappe.get_all(dt, fields=["name", "zip_code"], limit_page_length=200000)
    idx = { (r.get("zip_code") or "").strip().zfill(5): r["name"] for r in existing }

    def read_with(delim):
        with open(path, "r", encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f, delimiter=delim))

    # Try pipe first (2025), fallback to tab
    rows = read_with("|")
    if not rows or (len(rows) == 1 and len(rows[0]) == 1):
        rows = read_with("\t")

    created = 0
    updated = 0
    skipped = 0

    for row in rows:
        z = (row.get("GEOID") or row.get("ZCTA5") or "").strip()
        if not z:
            skipped += 1
            continue
        z = z.zfill(5)

        # lat/lng strings like '+18.180555'
        lat_s = (row.get("INTPTLAT") or row.get("INTPTLAT20") or "").strip().replace("+", "")
        lng_s = (row.get("INTPTLONG") or row.get("INTPTLON") or row.get("INTPTLONG20") or "").strip().replace("+", "")
        if not lat_s or not lng_s:
            skipped += 1
            continue

        try:
            lat = float(lat_s); lng = float(lng_s)
        except Exception:
            skipped += 1
            continue

        # square miles if present
        def _f(k):
            try: return float((row.get(k) or "0").strip())
            except Exception: return 0.0
        land = _f("ALAND_SQMI")
        water = _f("AWATER_SQMI")
        sqmi = land + water if (land or water) else None

        name = idx.get(z)
        if name:
            # update
            vals = {
                "centroid_latitude": lat,
                "centroid_longitude": lng
            }
            if sqmi is not None:
                vals["square_miles"] = sqmi
            frappe.db.set_value(dt, name, vals)
            updated += 1
        else:
            # create
            doc = {
                "doctype": dt,
                "zip_code": z,
                "centroid_latitude": lat,
                "centroid_longitude": lng,
            }
            if sqmi is not None:
                doc["square_miles"] = sqmi
            try:
                inserted = frappe.get_doc(doc).insert(ignore_permissions=True)
                idx[z] = inserted.name
                created += 1
            except Exception:
                skipped += 1

    frappe.db.commit()
    return {"created": created, "updated": updated, "skipped": skipped}

@frappe.whitelist()
def import_zip_state_crosswalk(path: str, zip_col="zip", state_col="state_code"):
    """Upsert state_code on Zip Code Analytics from a CSV crosswalk."""
    updated = 0
    with open(path, "r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            z = (row.get(zip_col) or "").strip().zfill(5)
            st = (row.get(state_col) or "").strip().upper()
            if not z or not st: continue
            name = frappe.db.get_value("Zip Code Analytics", {"zip_code": z}, "name")
            if name:
                frappe.db.set_value("Zip Code Analytics", name, "state_code", st)
                updated += 1
    frappe.db.commit()
    return {"updated": updated}

@frappe.whitelist()
def geocode_one_zip(zip_code: str):
    key = frappe.db.get_single_value("Google Maps Settings","api_key")
    if not key:
        frappe.throw("Google API key missing in Google Maps Settings")
    z = zip_code.strip().zfill(5)
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": f"{z} USA", "components": f"postal_code:{z}|country:US", "key": key}
    resp = requests.get(url, params=params, timeout=12).json()
    loc = (resp.get("results") or [{}])[0].get("geometry",{}).get("location",{})
    lat, lng = loc.get("lat"), loc.get("lng")
    if lat is None or lng is None:
        frappe.throw(f"Could not geocode ZIP {z}")
    name = frappe.db.get_value("Zip Code Analytics", {"zip_code": z}, "name")
    if not name:
        frappe.get_doc({
            "doctype": "Zip Code Analytics",
            "zip_code": z,
            "centroid_latitude": float(lat),
            "centroid_longitude": float(lng),
        }).insert(ignore_permissions=True)
    else:
        frappe.db.set_value("Zip Code Analytics", name, {
            "centroid_latitude": float(lat),
            "centroid_longitude": float(lng),
        })
    frappe.db.commit()
    return {"zip_code": z, "lat": float(lat), "lng": float(lng)}