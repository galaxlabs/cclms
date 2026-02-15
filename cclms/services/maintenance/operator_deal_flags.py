import frappe

def before_save_operator_deal(doc, method=None):
    """
    Allow maintenance/backfill scripts to bypass strict duplicate validation
    when explicitly requested via frappe.flags.
    """
    if getattr(frappe.flags, "maintenance_mode", False):
        doc.flags.skip_strict_duplicate_validation = True
