import frappe
import base64
import frappe
from frappe.utils.file_manager import save_file

def save_base64_image(base64_str, employee_id):
    """
    Decodes a base64 string and saves it as a private file in Frappe.
    """
    if not base64_str:
        return None

    # Clean the base64 string if it contains the header (data:image/jpeg;base64,...)
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]

    # Create a unique filename
    filename = f"snap_{employee_id}_{frappe.utils.now().replace(' ', '_')}.jpg"
    
    # Save the file to the 'private' folder
    # This automatically creates a 'File' document and returns the file_url
    file_doc = save_file(
        fname=filename,
        content=base64_str,
        doctype="Employee Activity Log",
        docname=None, # Will link later or leave empty for general storage
        is_private=1,
        decode=True
    )
    
    return file_doc.file_url



@frappe.whitelist()
def upload_activity_snap(employee, screenshot_base64, active_app):
    # 1. Find or Create Today's Session
    session_name = get_or_create_daily_session(employee)
    
    # 2. (Optional) Run Atomic Agent here to get 'ai_summary'
    # For testing, we will just save the raw data first
    
    doc = frappe.get_doc("Employee Activity Log", session_name)
    doc.append("activity_logs", {
        "event_time": frappe.utils.now_datetime(),
        "event_type": "Screen Snap",
        "screenshot": save_base64_image(screenshot_base64),
        "summary": f"User was active in {active_app}"
    })
    doc.save()
    return {"status": "success", "session": session_name}

def save_base64_image(base64_str, employee_id, session_name):
    if not base64_str:
        return None

    if "," in base64_str:
        base64_str = base64_str.split(",")[1]

    filename = f"snap_{employee_id}_{frappe.utils.now().replace(' ', '_')}.jpg"
    
    file_doc = save_file(
        fname=filename,
        content=base64_str,
        doctype="Employee Activity Log",
        docname=session_name, # Link it to the parent session
        is_private=1,
        decode=True
    )
    
    return file_doc.file_url

def get_or_create_daily_session(employee):
    today = frappe.utils.nowdate()
    existing = frappe.db.get_value("Employee Activity Log", {"employee": employee, "date": today})
    if existing:
        return existing
    
    new_doc = frappe.get_doc({
        "doctype": "Employee Activity Log",
        "employee": employee,
        "date": today,
        "status": "Active"
    })
    new_doc.insert(ignore_permissions=True)
    return new_doc.name