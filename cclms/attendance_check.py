import frappe
from frappe.utils import nowdate

def auto_check_in(login_manager):
    # Get the logged-in user's email (user_id)
    user_email = frappe.session.user

    # Fetch the corresponding Employee record based on user email
    employee = frappe.db.get_value('Employee', {'user_id': user_email}, ['name', 'attendance_device_id'], as_dict=True)

    if employee:
        # Fetch the username from the User document
        user = frappe.get_doc('User', user_email)
        username = user.username

        # Check if attendance_device_id matches the username or email
        if employee.attendance_device_id == user_email or employee.attendance_device_id == username:
            # Create an attendance record
            attendance_exists = frappe.db.exists('Attendance', {
                'employee': employee.name,
                'attendance_date': nowdate()
            })

            if not attendance_exists:
                # Create new attendance record
                attendance = frappe.get_doc({
                    'doctype': 'Attendance',
                    'employee': employee.name,
                    'attendance_date': nowdate(),
                    'status': 'Present'
                })
                attendance.insert(ignore_permissions=True)
                frappe.db.commit()
                frappe.msgprint(f"Auto Check-In Successful for {employee.name}")
        else:
            frappe.msgprint(f"Auto Check-In Failed: Device ID does not match for {employee.name}")
    else:
        frappe.msgprint(f"No Employee record found for user: {user_email}")
