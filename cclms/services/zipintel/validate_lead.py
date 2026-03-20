import frappe

from cclms.services.zipintel.intelligence import build_lead_intelligence


def validate_lead_zip(doc, _):
    """
    Lightweight pre-save helper.
    Keeps the old red-zone behavior, but now also checks competitor truth
    and same-ZIP lead spacing before allowing operator-facing progression.
    """
    zip_code = getattr(doc, "zip_code", None) or getattr(doc, "zip", None)
    if not zip_code:
        return

    snapshot = build_lead_intelligence(doc, write_zip_centroid=True)

    if hasattr(doc, "zone_color"):
        doc.zone_color = snapshot.get("zone_color")
    if hasattr(doc, "zone"):
        doc.zone = snapshot.get("matched_rule") or snapshot.get("zone_color")

    if not snapshot.get("qualified_for_approval"):
        frappe.throw(snapshot.get("recommended_next_action"))

