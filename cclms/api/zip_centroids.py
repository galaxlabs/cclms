# cclms/api/zip_centroids.py
from __future__ import annotations

import io
import csv
import zipfile
from typing import Dict, Any, Optional, Tuple, List

import frappe

DT = "Zip Code Analytics"

# ------------------ helpers ------------------

def _zpad5(z: Any) -> str:
    """Pad ZIP/ZCTA to 5 chars, clean '77001.0' from Excel-like inputs."""
    s = ("" if z is None else str(z)).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(5) if s else s

def _to_float(v) -> Optional[float]:
    """Safe float with commas and leading '+' stripped."""
    try:
        if v is None:
            return None
        s = str(v).strip().replace(",", "").replace("+", "")
        if s == "" or s.lower() == "null":
            return None
        return float(s)
    except Exception:
        return None

def _read_file_content(file_docname: str) -> bytes:
    """Fetch raw bytes from a File doctype row."""
    f = frappe.get_doc("File", file_docname)
    return f.get_content()

def _extract_inner_table(raw: bytes) -> str:
    """
    Accepts:
      - Raw .txt (returns decoded text)
      - .zip that contains Gazetteer .txt (returns decoded text of inner file)
    Tries UTF-8 decode; ignores errors if any strange chars.
    """
    # Is it a ZIP?
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            # pick first .txt or .csv inside
            inner_name = None
            for info in zf.infolist():
                name = info.filename.lower()
                if name.endswith(".txt") or name.endswith(".csv"):
                    inner_name = info.filename
                    break
            if not inner_name:
                frappe.throw("No .txt/.csv found inside the Gazetteer ZIP.")
            inner = zf.read(inner_name)
            return inner.decode("utf-8", errors="ignore")
    except zipfile.BadZipFile:
        # Not a zip, treat as plain text
        return raw.decode("utf-8", errors="ignore")

def _parse_gazetteer(text: str) -> List[Dict[str, Any]]:
    """
    Parse Gazetteer text. 2025 is typically pipe-delimited ('|').
    Fallback to tab if needed.
    Returns list of dict rows with original headers.
    """
    rows: List[Dict[str, Any]] = []

    def _read_with(delim: str) -> List[Dict[str, Any]]:
        buff = io.StringIO(text)
        r = csv.DictReader(buff, delimiter=delim)
        return [row for row in r]

    # Try pipe first, fallback to tab
    data = _read_with("|")
    if not data or (len(data) == 1 and len(data[0]) <= 1):
        data = _read_with("\t")

    # Some files have leading/trailing spaces in headers; normalize keys later when reading values.
    return data

def _get_existing_index() -> Dict[str, str]:
    """Build index: zip_code -> name for fast upsert."""
    existing = frappe.get_all(DT, fields=["name", "zip_code"], limit_page_length=200000)
    return { (r.get("zip_code") or "").strip().zfill(5): r["name"] for r in existing }

# ------------------ core logic ------------------

def _extract_fields(row: Dict[str, Any]) -> Tuple[Optional[str], Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Pull expected fields from a row (case-insensitive):
      GEOID, INTPTLAT, INTPTLONG, ALAND_SQMI, AWATER_SQMI
    Returns: (zcta, lat, lon, land_sq_mi, water_sq_mi)
    """
    # Normalize lookup (upper)
    up = { (k or "").upper().strip(): v for k, v in row.items() }

    zcta = _zpad5(up.get("GEOID") or up.get("ZCTA5") or up.get("GEOID10") or up.get("ZCTA5CE10"))
    lat  = _to_float(up.get("INTPTLAT")  or up.get("INTPTLAT20")  or up.get("INTPT_LAT")  or up.get("INTPTLAT10"))
    lon  = _to_float(up.get("INTPTLONG") or up.get("INTPTLON")    or up.get("INTPT_LONG") or up.get("INTPTLONG10"))
    land = _to_float(up.get("ALAND_SQMI") or up.get("ALAND_SQMI20") or up.get("ALANDMI"))
    water= _to_float(up.get("AWATER_SQMI") or up.get("AWATER_SQMI20") or up.get("AWATERMI"))

    return zcta, lat, lon, land, water

def _upsert_one(idx: Dict[str, str], z: str, lat: Optional[float], lon: Optional[float],
                land_sq_mi: Optional[float], water_sq_mi: Optional[float], dry_run: bool) -> Tuple[bool, bool]:
    """
    Upsert a single ZCTA row into Zip Code Analytics.
    Returns (created, updated).
    """
    if not z:
        return False, False

    # Compute total square_miles if both provided
    square_miles = None
    if land_sq_mi is not None or water_sq_mi is not None:
        square_miles = (land_sq_mi or 0.0) + (water_sq_mi or 0.0)

    name = idx.get(z)
    if name:
        # update existing
        vals = {}
        if lat is not None:  vals["latitude"] = lat
        if lon is not None:  vals["longitude"] = lon
        if land_sq_mi is not None:  vals["land_sq_mi"] = land_sq_mi
        if water_sq_mi is not None: vals["water_sq_mi"] = water_sq_mi
        if square_miles is not None: vals["square_miles"] = square_miles

        if not vals:
            return False, False

        if dry_run:
            return False, True

        frappe.db.set_value(DT, name, vals)
        return False, True

    else:
        # create new
        doc = {
            "doctype": DT,
            "zip_code": z,
        }
        if lat is not None:  doc["latitude"] = lat
        if lon is not None:  doc["longitude"] = lon
        if land_sq_mi is not None:  doc["land_sq_mi"] = land_sq_mi
        if water_sq_mi is not None: doc["water_sq_mi"] = water_sq_mi
        if square_miles is not None: doc["square_miles"] = square_miles

        if dry_run:
            return True, False

        inserted = frappe.get_doc(doc).insert(ignore_permissions=True)
        idx[z] = inserted.name
        return True, False

# ------------------ public API ------------------

@frappe.whitelist(methods=["POST"])
def import_zcta_centroids_2025(file_docname: str, limit: int = 0, dry_run: int = 0) -> Dict[str, Any]:
    """
    Import/Upsert ZCTA centroids & area from **2025_Gaz_zcta_national** (TXT or ZIP uploaded to File).

    - file_docname: File doctype name for 2025_Gaz_zcta_national.zip or .txt
    - limit: process first N rows (0 = all)
    - dry_run: 1 = do not write, just count

    Writes/updates fields on 'Zip Code Analytics':
      - zip_code (from GEOID, 5-digit)
      - latitude (INTPTLAT)
      - longitude (INTPTLONG)
      - land_sq_mi (ALAND_SQMI)
      - water_sq_mi (AWATER_SQMI)
      - square_miles = land_sq_mi + water_sq_mi
    """
    if not frappe.db.table_exists(DT):
        frappe.throw(f"{DT} doctype not found")

    raw = _read_file_content(file_docname)
    text = _extract_inner_table(raw)
    rows = _parse_gazetteer(text)

    idx = _get_existing_index()
    created = 0
    updated = 0
    skipped = 0

    n = 0
    for row in rows:
        if limit and n >= int(limit):
            break
        n += 1

        try:
            z, lat, lon, land, water = _extract_fields(row)
            if not z:
                skipped += 1
                continue

            c, u = _upsert_one(idx, z, lat, lon, land, water, dry_run=bool(int(dry_run)))
            created += 1 if c else 0
            updated += 1 if u else 0

        except Exception:
            skipped += 1

    if not bool(int(dry_run)):
        frappe.db.commit()

    return {
        "ok": True,
        "processed": n,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "dry_run": bool(int(dry_run)),
    }
@frappe.whitelist(methods=["POST"])
def import_zcta_centroids_2025_path(path: str, limit: int = 0, dry_run: int = 0):
    """
    Same as import_zcta_centroids_2025, but reads directly from a TXT/ZIP path on disk.
    Useful when you've placed the Gazetteer file under sites/<site>/private/files.
    """
    import os
    if not frappe.db.table_exists(DT):
        frappe.throw(f"{DT} doctype not found")

    if not os.path.exists(path):
        frappe.throw(f"File not found: {path}")

    # Load bytes
    with open(path, "rb") as f:
        raw = f.read()

    # Reuse the same internals as file_docname version
    text = _extract_inner_table(raw)
    rows = _parse_gazetteer(text)

    idx = _get_existing_index()
    created = 0
    updated = 0
    skipped = 0

    n = 0
    for row in rows:
        if limit and n >= int(limit):
            break
        n += 1
        try:
            z, lat, lon, land, water = _extract_fields(row)
            if not z:
                skipped += 1
                continue
            c, u = _upsert_one(idx, z, lat, lon, land, water, dry_run=bool(int(dry_run)))
            created += 1 if c else 0
            updated += 1 if u else 0
        except Exception:
            skipped += 1

    if not bool(int(dry_run)):
        frappe.db.commit()

    return {
        "ok": True,
        "processed": n,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "dry_run": bool(int(dry_run)),
    }
