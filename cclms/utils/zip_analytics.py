import frappe


def get_zip_row_by_zip(zip_code):
    # Dummy fallback until implemented
    return {
        "zip": zip_code,
        "analytics_flag": "Yes",
        "blended_pop_estimate": 10000,
        "square_miles": 5.2,
        "kiosks_pending_removal": 1
    }
