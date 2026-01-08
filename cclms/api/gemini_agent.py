# cclms/api/gemini_agent.py

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from cclms.services.zipintel.rules import classify_zip_row

import frappe
import requests

PLACES_TEXT_SEARCH_NEW = "https://places.googleapis.com/v1/places:searchText"
GEMINI_GENERATE_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"


def _get_places_key() -> str:
    # Prefer your Single doctype setting
    key = frappe.db.get_single_value("Google Maps Settings", "api_key")
    if not key:
        # optional fallback if you store in common_site_config.json
        key = frappe.conf.get("maps_api_key") or frappe.conf.get("maps_key")
    if not key:
        frappe.throw("Missing Google Places key. Set Google Maps Settings → api_key.")
    return key


def _get_gemini_key() -> str:
    key = frappe.conf.get("gemini_api_key")
    if not key:
        frappe.throw('Missing gemini_api_key in site config (frappe.conf).')
    return key


def _get_gemini_model() -> str:
    # Keep configurable
    return frappe.conf.get("gemini_model") or "gemini-2.5-flash"


def _get_business_types() -> List[str]:
    rows = frappe.get_all("Business Types", fields=["business_type"], order_by="business_type asc")
    kws = [(r.get("business_type") or "").strip() for r in rows]
    kws = [k for k in kws if k]
    if not kws:
        frappe.throw("Business Types is empty. Add keywords like 'Gas Station', 'Convenience Store', etc.")
    return kws


def _get_target_zips(limit_zips: int = 20):
    rows = frappe.get_all(
        "Zip Code Analytics",
        fields=[
            "zip_code", "latitude", "longitude",
            "population", "population_density", "zip_score",
            "company_kiosks", "competitor_kiosks", "total_kiosks",
            "kiosks_installed", "kiosks_removed", "kiosks_pending_removal",
        ],
        filters={"latitude": ["is", "set"], "longitude": ["is", "set"]},
        order_by="zip_score desc, population_density desc",
        limit_page_length=300,
    )

    out = []
    for r in rows:
        zone, rule = classify_zip_row(r)
        if zone in ("Green", "Light Green"):
            r["zone_color"] = zone
            r["matched_rule"] = rule
            r["zip_code"] = str(r.get("zip_code") or "").zfill(5)
            out.append(r)
        if len(out) >= limit_zips:
            break
    return out

# def _get_target_zips(limit_zips: int) -> List[Dict[str, Any]]:
#     # Use your zone_color directly (fast, simple)
#     rows = frappe.get_all(
#         "Zip Code Analytics",
#         fields=[
#             "zip_code",
#             "latitude",
#             "longitude",
#             "population",
#             "population_density",
#             "total_kiosks",
#             "company_kiosks",
#             "competitor_kiosks",
#             "zip_score",
#             "zone_color",
#         ],
#         filters={
#             "zone_color": ["in", ["Green", "Light Green"]],
#             "latitude": ["is", "set"],
#             "longitude": ["is", "set"],
#         },
#         order_by="zip_score desc, population_density desc",
#         limit_page_length=int(limit_zips),
#     )
#     for r in rows:
#         r["zip_code"] = str(r.get("zip_code") or "").zfill(5)
#     return rows


def _places_text_search_new(
    api_key: str,
    query: str,
    lat: float,
    lng: float,
    radius_m: int,
    max_results: int,
) -> List[Dict[str, Any]]:
    headers = {
        "X-Goog-Api-Key": api_key,
        # FieldMask required; only request what we need :contentReference[oaicite:1]{index=1}
        "X-Goog-FieldMask": (
            "places.id,"
            "places.displayName,"
            "places.formattedAddress,"
            "places.location,"
            "places.types,"
            "places.nationalPhoneNumber,"
            "places.websiteUri,"
            "places.rating,"
            "places.userRatingCount,"
            "places.addressComponents"
        ),
        "Content-Type": "application/json",
    }

    body = {
        "textQuery": query,
        "maxResultCount": int(max_results),
        "locationBias": {
            "circle": {
                "center": {"latitude": float(lat), "longitude": float(lng)},
                "radius": int(radius_m),
            }
        },
    }

    resp = requests.post(PLACES_TEXT_SEARCH_NEW, headers=headers, json=body, timeout=25)
    if resp.status_code >= 400:
        frappe.log_error(resp.text, f"Places searchText error ({resp.status_code})")
        return []

    data = resp.json() or {}
    return data.get("places") or []


def _extract_from_address_components(place: Dict[str, Any]) -> Tuple[str, str, str]:
    """
    Return (zip, city, state_code) if available.
    """
    zip_code = ""
    city = ""
    state = ""

    comps = place.get("addressComponents") or []
    for c in comps:
        types = c.get("types") or []
        text = (c.get("shortText") or c.get("longText") or "").strip()

        if "postal_code" in types and not zip_code:
            zip_code = text
        if ("locality" in types or "postal_town" in types) and not city:
            city = text
        if "administrative_area_level_1" in types and not state:
            state = text

    return zip_code, city, state


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _gemini_score(payload: Dict[str, Any]) -> Dict[str, Any]:
    key = _get_gemini_key()
    model = _get_gemini_model()
    url = GEMINI_GENERATE_TMPL.format(model=model, key=key)

    prompt = f"""
Return ONLY valid JSON with keys:
{{
  "score": <number 1-100>,
  "pitch": "<one sentence pitch>",
  "reasoning": "<one short paragraph>"
}}

Business:
- name: {payload.get("business_name")}
- address: {payload.get("address")}
- types: {payload.get("types")}

Zip Intelligence:
- zip: {payload.get("zip_code")}
- population: {payload.get("population")}
- population_density: {payload.get("population_density")}
- total_kiosks: {payload.get("total_kiosks")}
- competitor_kiosks: {payload.get("competitor_kiosks")}
- company_kiosks: {payload.get("company_kiosks")}
- zip_score: {payload.get("zip_score")}
""".strip()

    req = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 350},
    }

    r = requests.post(url, json=req, timeout=30)
    if r.status_code >= 400:
        frappe.log_error(r.text, f"Gemini generateContent error ({r.status_code})")
        return {"score": 0, "pitch": "", "reasoning": "Gemini call failed", "raw": ""}

    data = r.json() or {}
    text = ""
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        pass

    js = _extract_json(text) or {}
    return {
        "score": float(js.get("score") or 0),
        "pitch": (js.get("pitch") or "").strip(),
        "reasoning": (js.get("reasoning") or "").strip(),
        "raw": text,
    }


def _is_duplicate(address: str, zip_code: str) -> Optional[str]:
    """
    If we find another BTM Opportunity with same address+zip, return its name.
    """
    if not address or not zip_code:
        return None
    existing = frappe.db.get_value(
        "BTM Opportunity",
        {"address": address, "zip_code": zip_code},
        "name"
    )
    return existing


def _create_btm_opportunity(place: Dict[str, Any], zip_row: Dict[str, Any], kw: str, ai: Dict[str, Any]) -> bool:
    place_id = place.get("id")
    if not place_id:
        return False

    # Hard dedupe on place_id (your field is unique)
    if frappe.db.exists("BTM Opportunity", {"place_id": place_id}):
        return False

    display_name = ((place.get("displayName") or {}).get("text") or "").strip()
    formatted_address = (place.get("formattedAddress") or "").strip()

    loc = place.get("location") or {}
    lat = loc.get("latitude")
    lng = loc.get("longitude")

    # Extract from address components, but keep ZIP from analytics as primary
    place_zip, city, state = _extract_from_address_components(place)

    zip_code = str(zip_row.get("zip_code") or "").zfill(5)
    dup_of = _is_duplicate(formatted_address, zip_code)

    doc = frappe.new_doc("BTM Opportunity")
    doc.place_id = place_id
    doc.business_name = display_name or "Unknown"
    doc.address = formatted_address
    doc.city = city
    doc.state_code = state
    doc.zip_code = zip_code
    doc.latitude = float(lat) if lat is not None else None
    doc.longitude = float(lng) if lng is not None else None

    # Business type is a Link → Business Types.
    # If your Business Types "name" equals kw, this works. Otherwise change to a map.
    try:
        doc.business_type = kw
    except Exception:
        pass

    doc.phone = (place.get("nationalPhoneNumber") or "")[:140]
    doc.website = str(place.get("websiteUri") or "")[:300]
    doc.google_rating = float(place.get("rating") or 0) if place.get("rating") is not None else None
    doc.user_ratings_total = int(place.get("userRatingCount") or 0) if place.get("userRatingCount") is not None else None

    doc.source = "gemini_agent"

    doc.ai_score = float(ai.get("score") or 0)
    doc.ai_pitch = ai.get("pitch") or ""
    doc.ai_reasoning = ai.get("reasoning") or ""
    doc.ai_analysis_html = f"<b>Score:</b> {doc.ai_score}<br><b>Pitch:</b> {frappe.utils.escape_html(doc.ai_pitch)}"

    if dup_of:
        doc.duplicate_check = 1
        doc.duplicate_of = dup_of
        doc.status = "Rejected"
    else:
        doc.status = "New"

    doc.insert(ignore_permissions=True)
    return True


@frappe.whitelist()
def run_now(limit_zips: int = 2, min_ai_score: float = 80, radius_m: int = 12000, max_places_per_type: int = 15) -> Dict[str, Any]:
    places_key = _get_places_key()
    business_keywords = _get_business_types()
    zips = _get_target_zips(int(limit_zips))

    created = 0
    scanned = 0

    for zr in zips:
        lat = float(zr["latitude"])
        lng = float(zr["longitude"])
        zip_code = zr["zip_code"]

        for kw in business_keywords:
            # Improve relevance by anchoring to zip
            query = f"{kw} near {zip_code}"

            places = _places_text_search_new(
                api_key=places_key,
                query=query,
                lat=lat,
                lng=lng,
                radius_m=int(radius_m),
                max_results=int(max_places_per_type),
            )

            for p in places:
                scanned += 1

                payload = {
                    "business_name": ((p.get("displayName") or {}).get("text") or ""),
                    "address": (p.get("formattedAddress") or ""),
                    "types": p.get("types") or [],
                    "zip_code": zip_code,
                    "population": zr.get("population"),
                    "population_density": zr.get("population_density"),
                    "total_kiosks": zr.get("total_kiosks"),
                    "competitor_kiosks": zr.get("competitor_kiosks"),
                    "company_kiosks": zr.get("company_kiosks"),
                    "zip_score": zr.get("zip_score"),
                }

                ai = _gemini_score(payload)
                if (ai.get("score") or 0) < float(min_ai_score):
                    continue

                if _create_btm_opportunity(p, zr, kw, ai):
                    created += 1

                time.sleep(0.2)  # throttle

    frappe.db.commit()
    return {"zips_scanned": len(zips), "places_scanned": scanned, "opportunities_created": created}


def run_minutely():
    # small run for frequent scheduling
    try:
        run_now(limit_zips=1, min_ai_score=80, radius_m=12000, max_places_per_type=10)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "BTM Agent (minutely) failed")

# import frappe
# import requests
# import json
# import google.generativeai as genai
# from frappe import _

# @frappe.whitelist()
# def scrape_and_analyze_locations():
#     """
#     Silent Agent (Scheduled Task):
#     1. Scans Zip Code Analytics for high-potential areas.
#     2. Scrapes Google Maps for target businesses (Gas Stations, etc).
#     3. Uses Gemini to analyze and create BTM Opportunities.
#     """
#     # 1. Configuration & API Keys
#     api_key = frappe.conf.get("gemini_api_key")
#     google_key = frappe.conf.get("google_maps_key")
    
#     if not api_key or not google_key:
#         frappe.log_error("Missing Gemini or Google Maps API Keys in site_config", "BTM Agent Error")
#         return "Missing API Keys"

#     genai.configure(api_key=api_key)
#     model = genai.GenerativeModel('gemini-pro')

#     # 2. Identify Top 5 High-Potential Zips from your imported Analytics
#     # We look for areas with high population but low current machine count
#     target_zips = frappe.get_all("Zip Code Analytics", 
#         filters={"population": [">", 25000], "total_kiosks": ["<", 5]},
#         fields=["zip_code", "population", "city", "state_code"],
#         limit=5, order_by="population desc"
#     )

#     count_created = 0
#     for z in target_zips:
#         # 3. Scrape Google Maps for businesses in this Zip
#         # We query for business types you typically target (Gas Stations, Laundries, etc.)
#         search_query = f"gas station in {z.zip_code} {z.city}"
#         businesses = fetch_places_from_google(search_query, google_key)
        
#         for biz in businesses:
#             place_id = biz.get('place_id')
            
#             # Deduplication: Don't create if it exists in Opportunities or ATM Leads
#             if check_if_exists(place_id):
#                 continue

#             # 4. Silent AI Evaluation: Gemini determines if it's a good "Opportunity"
#             analysis = get_gemini_score(model, biz, z)
            
#             # We only create the opportunity if the AI score is high (e.g., 75+)
#             if analysis.get('score', 0) >= 75:
#                 create_btm_opportunity(biz, analysis, z)
#                 count_created += 1
                
#     return f"Silent Agent Finished. Created {count_created} new opportunities."

# def fetch_places_from_google(query, api_key):
#     """Calls Google Places Text Search API"""
#     url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
#     params = {"query": query, "key": api_key}
#     try:
#         r = requests.get(url, params=params)
#         return r.json().get('results', [])
#     except Exception as e:
#         frappe.log_error(f"Google Maps Scrape Failed: {str(e)}")
#         return []

# def get_gemini_score(model, biz, zip_data):
#     """Asks Gemini to analyze the business potential based on Zip data"""
#     prompt = f"""
#     Context: We are placing Bitcoin ATMs in high-traffic retail locations.
#     Business Name: {biz.get('name')}
#     Address: {biz.get('formatted_address')}
#     Google Rating: {biz.get('rating')} ({biz.get('user_ratings_total')} reviews)
#     Area Population: {zip_data.population}
    
#     Task: Evaluate market fit. Return ONLY a JSON object:
#     {{
#       "score": (int 1-100),
#       "pitch": (one-sentence sales hook),
#       "reasoning": (short logic)
#     }}
#     """
#     try:
#         response = model.generate_content(prompt)
#         # Clean response for JSON parsing
#         raw_text = response.text.strip().replace('```json', '').replace('```', '')
#         return json.loads(raw_text)
#     except:
#         return {"score": 0, "pitch": "Manual review needed.", "reasoning": "AI call failed."}

# def create_btm_opportunity(biz, ai, zip_data):
#     """Inserts a new 'BTM Opportunity' record into Frappe"""
#     doc = frappe.get_doc({
#         "doctype": "BTM Opportunity",
#         "place_id": biz['place_id'],
#         "business_name": biz['name'],
#         "address": biz.get('formatted_address'),
#         "city": zip_data.city,
#         "state_code": zip_data.state_code,
#         "zip_code": zip_data.zip_code,
#         "latitude": biz['geometry']['location']['lat'],
#         "longitude": biz['geometry']['location']['lng'],
#         "google_rating": biz.get('rating'),
#         "user_ratings_total": biz.get('user_ratings_total'),
#         "source": "gemini_agent",
#         "ai_score": ai.get('score'),
#         "ai_pitch": ai.get('pitch'),
#         "ai_reasoning": ai.get('reasoning'),
#         "status": "New",
#         # Custom HTML Scorecard for the desk view
#         "ai_analysis_html": f"""
#             <div style="background:#eef2ff; border-left:4px solid #4f46e5; padding:12px; border-radius:4px;">
#                 <b style="color:#4f46e5; font-size:16px;">AI Market Score: {ai.get('score')}/100</b><br>
#                 <i style="color:#374151;">"{ai.get('pitch')}"</i>
#             </div>
#         """
#     })
#     doc.insert(ignore_permissions=True)
#     frappe.db.commit()

# def check_if_exists(place_id):
#     """Strict duplicate check using Place ID"""
#     if frappe.db.exists("BTM Opportunity", {"place_id": place_id}):
#         return True
#     if frappe.db.exists("ATM Leads", {"place_id": place_id}):
#         return True
#     return False

# @frappe.whitelist()
# def convert_to_lead(opp_name, note=""):
#     """Logic for the 'Convert to ATM Lead' button"""
#     opp = frappe.get_doc("BTM Opportunity", opp_name)
    
#     if opp.status == "Converted":
#         frappe.throw(_("This opportunity is already converted to a Lead."))

#     # 1. Create the new ATM Lead
#     lead = frappe.get_doc({
#         "doctype": "ATM Leads",
#         "business_name": opp.business_name,
#         "address": opp.address,
#         "city": opp.city,
#         "state_code": opp.state_code,
#         "zippostal_code": opp.zip_code,
#         "latitude": opp.latitude,
#         "longitude": opp.longitude,
#         "workflow_status": "Pending Review", # Set your default status
#         "notes": f"Converted from Opportunity: {opp.name}. {note}"
#     })
#     lead.insert(ignore_permissions=True)

#     # 2. Update Opportunity to hide button and link records
#     opp.status = "Converted"
#     opp.lead = lead.name
#     opp.conversion_note = note
#     opp.reviewed_by = frappe.session.user
#     opp.reviewed_on = frappe.utils.now_datetime()
#     opp.save(ignore_permissions=True)
    
#     frappe.db.commit()
#     return lead.name
# import json
# import re
# import time
# from typing import Dict, Any, List, Optional, Tuple

# import frappe
# import requests

# from cclms.services.zipintel.rules import classify_zip

# # Places API (New) - Text Search
# PLACES_TEXT_SEARCH_NEW = "https://places.googleapis.com/v1/places:searchText"

# # Gemini API - generateContent
# # Docs: models.generateContent (Gemini API) :contentReference[oaicite:0]{index=0}
# GEMINI_GENERATE_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"


# # ----------------------------
# # Helpers: Keys / Settings
# # ----------------------------
# def _get_places_key() -> str:
#     key = frappe.db.get_single_value("Google Maps Settings", "api_key")
#     if not key:
#         # optional fallback if you store it in site config
#         key = frappe.conf.get("maps_api_key") or frappe.conf.get("maps_key")
#     if not key:
#         frappe.throw("Missing Google Places key. Set Google Maps Settings → api_key (recommended).")
#     return key


# def _get_gemini_key() -> str:
#     key = frappe.conf.get("gemini_api_key")
#     if not key:
#         frappe.throw('Missing gemini_api_key in site config (frappe.conf).')
#     return key


# def _get_gemini_model() -> str:
#     # Default to a modern “flash” model; override via common_site_config.json if you want.
#     # Model list changes over time; keep configurable. :contentReference[oaicite:1]{index=1}
#     return frappe.conf.get("gemini_model") or "gemini-2.5-flash"


# # ----------------------------
# # Helpers: Target ZIP selection
# # ----------------------------
# def _is_greenish(zone_name: str, color_code: str) -> bool:
#     z = (zone_name or "").lower()
#     c = (color_code or "").lower()
#     return ("green" in z) or ("green" in c)


# def _get_target_zips(limit_zips: int = 20) -> List[Dict[str, Any]]:
#     """
#     Pull the best ZIPs to scan. We do:
#     - sort by zip_score desc, then population_density desc
#     - evaluate rules (classify_zip) and keep "green-ish"
#     """
#     rows = frappe.get_all(
#         "Zip Code Analytics",
#         fields=[
#             "zip_code",
#             "latitude",
#             "longitude",
#             "population",
#             "population_density",
#             "total_kiosks",
#             "company_kiosks",
#             "competitor_kiosks",
#             "zip_score",
#             "state_code",
#         ],
#         filters={
#             "latitude": ["is", "set"],
#             "longitude": ["is", "set"],
#         },
#         order_by="zip_score desc, population_density desc",
#         limit_page_length=max(limit_zips * 5, 200),
#     )

#     out = []
#     for r in rows:
#         zip_code = str(r.get("zip_code") or "").zfill(5)
#         zone_name, color_code = classify_zip(zip_code)
#         if _is_greenish(zone_name, color_code):
#             r["zip_code"] = zip_code
#             r["zone_name"] = zone_name
#             r["zone_color_code"] = color_code
#             out.append(r)
#         if len(out) >= limit_zips:
#             break
#     return out


# # ----------------------------
# # Helpers: Places (New) Text Search
# # Text Search (New) reference :contentReference[oaicite:2]{index=2}
# # ----------------------------
# def _places_text_search_new(
#     api_key: str,
#     query: str,
#     lat: float,
#     lng: float,
#     radius_m: int,
#     max_results: int = 20,
# ) -> List[Dict[str, Any]]:
#     headers = {
#         "X-Goog-Api-Key": api_key,
#         # Choose fields; required in Places API (New) :contentReference[oaicite:3]{index=3}
#         "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.types",
#         "Content-Type": "application/json",
#     }

#     body = {
#         "textQuery": query,
#         "maxResultCount": max_results,
#         "locationBias": {
#             "circle": {
#                 "center": {"latitude": float(lat), "longitude": float(lng)},
#                 "radius": int(radius_m),
#             }
#         },
#     }

#     resp = requests.post(PLACES_TEXT_SEARCH_NEW, headers=headers, json=body, timeout=20)
#     if resp.status_code >= 400:
#         frappe.log_error(message=resp.text, title=f"Places searchText error ({resp.status_code})")
#         return []

#     data = resp.json() or {}
#     return data.get("places") or []


# # ----------------------------
# # Helpers: Gemini scoring
# # ----------------------------
# def _extract_json(text: str) -> Optional[Dict[str, Any]]:
#     if not text:
#         return None
#     # try direct json
#     try:
#         return json.loads(text)
#     except Exception:
#         pass
#     # try to find first json object in text
#     m = re.search(r"\{[\s\S]*\}", text)
#     if not m:
#         return None
#     try:
#         return json.loads(m.group(0))
#     except Exception:
#         return None


# def _gemini_score_business(payload: Dict[str, Any]) -> Dict[str, Any]:
#     key = _get_gemini_key()
#     model = _get_gemini_model()
#     url = GEMINI_GENERATE_TMPL.format(model=model, key=key)

#     prompt = f"""
# Act as a BTM Deployment Specialist for Bitcoin Depot.

# Return ONLY valid JSON with exactly these keys:
# {{
#   "score": <number 1-100>,
#   "pitch": "<one sentence pitch>",
#   "reasoning": "<one short paragraph>",
#   "is_duplicate": <true/false>
# }}

# Business:
# - name: {payload.get("name")}
# - address: {payload.get("address")}
# - types: {payload.get("types")}

# Zip Intelligence:
# - zip: {payload.get("zip_code")}
# - population: {payload.get("population")}
# - population_density: {payload.get("population_density")}
# - total_kiosks: {payload.get("total_kiosks")}
# - competitor_kiosks: {payload.get("competitor_kiosks")}
# - company_kiosks: {payload.get("company_kiosks")}
# - zip_score: {payload.get("zip_score")}
# """

#     req = {
#         "contents": [{"role": "user", "parts": [{"text": prompt.strip()}]}],
#         "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300},
#     }

#     r = requests.post(url, json=req, timeout=25)
#     if r.status_code >= 400:
#         frappe.log_error(message=r.text, title=f"Gemini generateContent error ({r.status_code})")
#         return {"score": 0, "pitch": "", "reasoning": "Gemini call failed", "is_duplicate": False}

#     data = r.json() or {}
#     text = ""
#     try:
#         text = data["candidates"][0]["content"]["parts"][0]["text"]
#     except Exception:
#         pass

#     js = _extract_json(text) or {}
#     return {
#         "score": float(js.get("score") or 0),
#         "pitch": (js.get("pitch") or "").strip(),
#         "reasoning": (js.get("reasoning") or "").strip(),
#         "is_duplicate": bool(js.get("is_duplicate") or False),
#         "raw": text,
#         "model": model,
#     }


# # ----------------------------
# # Helpers: Insert Opportunity (field-flexible)
# # ----------------------------
# def _first_field(meta, candidates: List[str]) -> Optional[str]:
#     fields = {f.fieldname for f in meta.fields}
#     for c in candidates:
#         if c in fields:
#             return c
#     return None


# def _upsert_btm_opportunity(place: Dict[str, Any], zip_row: Dict[str, Any], score: Dict[str, Any], business_keyword: str) -> bool:
#     doctype = "BTM Opportunity"
#     meta = frappe.get_meta(doctype)

#     pid = place.get("id")
#     if not pid:
#         return False

#     # Find best matching fieldnames
#     f_place_id = _first_field(meta, ["place_id", "google_place_id", "places_id"])
#     f_name     = _first_field(meta, ["business_name", "display_name", "name"])
#     f_address  = _first_field(meta, ["address", "formatted_address"])
#     f_zip      = _first_field(meta, ["zip_code", "zip", "zippostal_code"])
#     f_lat      = _first_field(meta, ["latitude", "lat"])
#     f_lng      = _first_field(meta, ["longitude", "lng"])
#     f_type     = _first_field(meta, ["business_type", "business_keyword", "keyword"])
#     f_score    = _first_field(meta, ["ai_score", "score"])
#     f_reason   = _first_field(meta, ["ai_reasoning", "ai_reason", "reasoning"])
#     f_pitch    = _first_field(meta, ["ai_pitch", "pitch"])
#     f_status   = _first_field(meta, ["status"])

#     # Dedupe: look up by place_id if that field exists, otherwise by name+zip+address
#     if f_place_id and frappe.db.exists(doctype, {f_place_id: pid}):
#         return False

#     disp = (place.get("displayName") or {}).get("text") or ""
#     addr = place.get("formattedAddress") or ""
#     loc = place.get("location") or {}
#     plat, plng = loc.get("latitude"), loc.get("longitude")

#     doc = frappe.new_doc(doctype)

#     if f_place_id:
#         doc.set(f_place_id, pid)
#     if f_name:
#         doc.set(f_name, disp)
#     if f_address:
#         doc.set(f_address, addr)
#     if f_zip:
#         doc.set(f_zip, zip_row.get("zip_code"))
#     if f_lat and plat is not None:
#         doc.set(f_lat, float(plat))
#     if f_lng and plng is not None:
#         doc.set(f_lng, float(plng))
#     if f_type:
#         doc.set(f_type, business_keyword)

#     if f_score:
#         doc.set(f_score, score.get("score") or 0)
#     if f_reason:
#         doc.set(f_reason, score.get("reasoning") or "")
#     if f_pitch:
#         doc.set(f_pitch, score.get("pitch") or "")

#     if f_status:
#         doc.set(f_status, "New")

#     doc.insert(ignore_permissions=True)
#     return True


# # ----------------------------
# # Main job (Scheduler + Manual)
# # ----------------------------
# @frappe.whitelist()
# def run_now(limit_zips: int = 10, min_ai_score: float = 80.0, radius_m: int = 12000, max_places_per_type: int = 20) -> Dict[str, Any]:
#     """
#     Manual run endpoint.
#     - Picks top 'green-ish' ZIPs
#     - For each ZIP, searches each Business Type via Places Text Search (New)
#     - Gemini scores each place and inserts BTM Opportunity if score >= min_ai_score
#     """
#     places_key = _get_places_key()

#     biz_types = frappe.get_all("Business Types", fields=["business_type"], order_by="business_type asc")
#     biz_keywords = [b["business_type"] for b in biz_types if (b.get("business_type") or "").strip()]

#     if not biz_keywords:
#         frappe.throw("Business Types is empty. Add keywords first (Gas Station, Convenience Store, etc.).")

#     zips = _get_target_zips(limit_zips=int(limit_zips))

#     created = 0
#     scanned_places = 0

#     for zr in zips:
#         lat = float(zr["latitude"])
#         lng = float(zr["longitude"])
#         zip_code = zr["zip_code"]

#         for kw in biz_keywords:
#             # Places Text Search (New) :contentReference[oaicite:4]{index=4}
#             places = _places_text_search_new(
#                 api_key=places_key,
#                 query=kw,
#                 lat=lat,
#                 lng=lng,
#                 radius_m=int(radius_m),
#                 max_results=int(max_places_per_type),
#             )

#             for p in places:
#                 scanned_places += 1

#                 payload = {
#                     "name": ((p.get("displayName") or {}).get("text") or ""),
#                     "address": (p.get("formattedAddress") or ""),
#                     "types": p.get("types") or [],
#                     "zip_code": zip_code,
#                     "population": zr.get("population"),
#                     "population_density": zr.get("population_density"),
#                     "total_kiosks": zr.get("total_kiosks"),
#                     "competitor_kiosks": zr.get("competitor_kiosks"),
#                     "company_kiosks": zr.get("company_kiosks"),
#                     "zip_score": zr.get("zip_score"),
#                 }

#                 score = _gemini_score_business(payload)
#                 if (score.get("score") or 0) < float(min_ai_score):
#                     continue
#                 if score.get("is_duplicate"):
#                     continue

#                 if _upsert_btm_opportunity(p, zr, score, kw):
#                     created += 1

#                 # gentle throttle (protects quotas)
#                 time.sleep(0.2)

#     frappe.db.commit()
#     return {"zips_scanned": len(zips), "places_scanned": scanned_places, "opportunities_created": created}


# def run_hourly_btm_agent():
#     """
#     Scheduler-friendly wrapper: smaller scan, cheaper.
#     """
#     try:
#         run_now(limit_zips=5, min_ai_score=80, radius_m=12000, max_places_per_type=15)
#     except Exception:
#         frappe.log_error(frappe.get_traceback(), "BTM Hourly Agent failed")
