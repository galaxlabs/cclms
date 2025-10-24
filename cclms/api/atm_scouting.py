import frappe
from typing import List, Dict

@frappe.whitelist()
def get_zip_circles():
    """
    Return centroids + styling for ZIP circles.
    - Uses Zip Code Analytics fields you actually have.
    - radius_meters is derived from square_miles when available, else default.
    """
    fields = [
        "zip_code",
        "zone_color",          # Select: Green / Light Green / Yellow / Red
        "zone",                # (optional) string zone; used if zone_color is empty
        "latitude",
        "longitude",
        "square_miles",        # used to derive radius
        "population",
        "margin",
        "competitor_kiosks",
        "zip_score",
        "state_code",
    ]

    rows = frappe.get_all("Zip Code Analytics", fields=fields, limit_page_length=200000)

    out = []
    for r in rows:
        lat = r.get("latitude")
        lng = r.get("longitude")
        if lat is None or lng is None:
            continue

        # Prefer zone_color; fallback to zone; else Unclassified
        zone = (r.get("zone_color") or r.get("zone") or "Unclassified").strip()

        # Derive radius:
        # - if square_miles is present, compute equivalent-circle radius and then 2× for visibility
        # - clamp to a reasonable range for map display (5–25 km)
        sqmi = r.get("square_miles")
        if sqmi is not None:
            try:
                import math
                eq_r_m = math.sqrt(float(sqmi) / math.pi) * 1609.34  # miles→meters
                radius_m = int(max(5_000, min(25_000, eq_r_m * 2)))
            except Exception:
                radius_m = 8_000
        else:
            radius_m = 8_000  # default ~5 mi

        out.append({
            "zip_code": r.get("zip_code"),
            "zone_color": zone,
            "latitude": float(lat),
            "longitude": float(lng),
            "radius_meters": radius_m,
            "population": r.get("population"),
            "margin": r.get("margin"),
            "competitor_kiosks": r.get("competitor_kiosks"),
            "zip_score": r.get("zip_score"),
            "state_code": r.get("state_code"),
        })

    return out
