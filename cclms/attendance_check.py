
import frappe
from frappe.utils import now_datetime, nowdate, get_time

import frappe
from frappe.utils import now_datetime, nowdate, get_time

def auto_check_in(login_manager):
    """This function is triggered on login to log check-in time based on shift timings and submit attendance."""
    user_email = frappe.session.user

    # Fetch the corresponding Employee record based on user email
    employee = frappe.db.get_value('Employee', {'user_id': user_email}, ['name', 'attendance_device_id'], as_dict=True)

    if employee:
        # Fetch the assigned shift for the employee from the Shift Assignment
        shift_assignment = frappe.db.get_value('Shift Assignment', {
            'employee': employee.name,
            'docstatus': 1,
            'start_date': ['<=', nowdate()],
            'end_date': ['>=', nowdate()]
        }, ['shift_type'], as_dict=True)

        if shift_assignment:
            # Fetch shift timings (start_time, end_time) from Shift Type
            shift_type = frappe.db.get_value('Shift Type', shift_assignment.shift_type, ['start_time', 'end_time'], as_dict=True)

            if shift_type:
                # Get the current time and compare it with shift start time
                current_time = get_time(now_datetime())
                shift_start_time = get_time(shift_type.start_time)
                shift_end_time = get_time(shift_type.end_time)

                # Determine if this is a late entry
                is_late = current_time > shift_start_time
                status = "Late" if is_late else "Present"

                # Check if an attendance record already exists for the day
                attendance_exists = frappe.db.exists('Attendance', {
                    'employee': employee.name,
                    'attendance_date': nowdate()
                })

                if not attendance_exists:
                    # Create and submit the attendance record
                    check_in_time = now_datetime()
                    attendance = frappe.get_doc({
                        'doctype': 'Attendance',
                        'employee': employee.name,
                        'attendance_date': nowdate(),
                        'status': status,
                        'shift': shift_assignment.shift_type,
                        'check_in': check_in_time,  # Log the current time as check-in
                        'shift_start_time': shift_type.start_time,
                        'late_entry': is_late
                    })
                    attendance.insert(ignore_permissions=True)
                    attendance.submit()  # Automatically submit the attendance
                    frappe.db.commit()
                    frappe.msgprint(f"{status} check-in logged and submitted for {employee.name} for shift {shift_assignment.shift_type}.")
                else:
                    frappe.msgprint(f"Check-in already recorded for {employee.name} today.")
            else:
                frappe.msgprint(f"Shift Type not found for assigned shift {shift_assignment.shift_type}.")
        else:
            frappe.msgprint(f"No shift assignment found for {employee.name}.")
    else:
        frappe.log_error(f"No employee found for user: {user_email}", "Auto Check-in Error")


def auto_check_out():
    """This function is triggered on logout to log check-out time based on shift timings, detect early exit, and submit attendance."""
    user_email = frappe.session.user

    # Fetch the corresponding Employee record based on user email
    employee = frappe.db.get_value('Employee', {'user_id': user_email}, ['name', 'attendance_device_id'], as_dict=True)

    if employee:
        # Fetch the assigned shift for the employee from the Shift Assignment
        shift_assignment = frappe.db.get_value('Shift Assignment', {
            'employee': employee.name,
            'docstatus': 1,
            'start_date': ['<=', nowdate()],
            'end_date': ['>=', nowdate()]
        }, ['shift_type'], as_dict=True)

        if shift_assignment:
            # Fetch shift timings (start_time, end_time) from Shift Type
            shift_type = frappe.db.get_value('Shift Type', shift_assignment.shift_type, ['start_time', 'end_time'], as_dict=True)

            if shift_type:
                # Get the current time and compare it with shift end time
                current_time = get_time(now_datetime())
                shift_end_time = get_time(shift_type.end_time)

                # Check if an attendance record exists for the day
                attendance = frappe.get_all('Attendance', filters={
                    'employee': employee.name,
                    'attendance_date': nowdate(),
                }, fields=['name', 'check_in', 'check_out'], limit=1)

                if attendance:
                    attendance_doc = frappe.get_doc('Attendance', attendance[0].name)

                    if not attendance_doc.check_out:
                        # Determine if this is an early exit
                        is_early = current_time < shift_end_time

                        # Log the current time as check-out and mark early exit if applicable
                        attendance_doc.check_out = now_datetime()
                        attendance_doc.early_exit = is_early
                        attendance_doc.save(ignore_permissions=True)
                        attendance_doc.submit()  # Automatically submit the updated attendance
                        frappe.db.commit()

                        if is_early:
                            frappe.msgprint(f"Early exit logged and submitted for {employee.name}.")
                        else:
                            frappe.msgprint(f"Check-out logged and submitted for {employee.name}.")
                    else:
                        frappe.msgprint(f"Check-out already recorded for {employee.name} today.")
                else:
                    frappe.msgprint(f"No check-in record found for {employee.name} today.")
            else:
                frappe.msgprint(f"Shift Type not found for assigned shift {shift_assignment.shift_type}.")
        else:
            frappe.msgprint(f"No shift assignment found for {employee.name}.")
    else:
        frappe.log_error(f"No employee found for user: {user_email}", "Auto Check-out Error")

# def auto_check_in(login_manager):
#     """This function is triggered on login to log check-in time and detect late entry, then submit attendance."""
#     user_email = frappe.session.user

#     # Fetch the corresponding Employee record based on user email
#     employee = frappe.db.get_value('Employee', {'user_id': user_email}, ['name', 'attendance_device_id'], as_dict=True)

#     if employee:
#         # Check if an attendance record exists for the day
#         attendance_exists = frappe.db.exists('Attendance', {
#             'employee': employee.name,
#             'attendance_date': nowdate()
#         })

#         current_time = get_time(now_datetime())

#         if not attendance_exists:
#             # Determine if this is a late entry
#             is_late = current_time > get_time(WORK_START_TIME)
#             status = "Late" if is_late else "Present"

#             # Create and submit the attendance record
#             attendance = frappe.get_doc({
#                 'doctype': 'Attendance',
#                 'employee': employee.name,
#                 'attendance_date': nowdate(),
#                 'status': status,
#                 'check_in': now_datetime(),  # Log the current time as check-in
#                 'late_entry': is_late
#             })
#             attendance.insert(ignore_permissions=True)
#             attendance.submit()  # Automatically submit the attendance
#             frappe.db.commit()
#             frappe.msgprint(f"{status} check-in logged and submitted for {employee.name}.")
#         else:
#             frappe.msgprint(f"Check-in already recorded for {employee.name} today.")
#     else:
#         frappe.log_error(f"No employee found for user: {user_email}", "Auto Check-in Error")


# def auto_check_out():
#     """This function is triggered on logout to log check-out time, detect early exit, and submit attendance."""
#     user_email = frappe.session.user

#     # Fetch the corresponding Employee record based on user email
#     employee = frappe.db.get_value('Employee', {'user_id': user_email}, ['name', 'attendance_device_id'], as_dict=True)

#     if employee:
#         # Check if an attendance record exists for the day and ensure check-out isn't already logged
#         attendance = frappe.get_all('Attendance', filters={
#             'employee': employee.name,
#             'attendance_date': nowdate(),
#         }, fields=['name', 'check_in', 'check_out'], limit=1)

#         current_time = get_time(now_datetime())

#         if attendance:
#             attendance_doc = frappe.get_doc('Attendance', attendance[0].name)

#             if not attendance_doc.check_out:
#                 # Determine if this is an early exit
#                 is_early = current_time < get_time(WORK_END_TIME)

#                 # Log the current time as check-out and mark early exit if applicable
#                 attendance_doc.check_out = now_datetime()
#                 attendance_doc.early_exit = is_early
#                 attendance_doc.save(ignore_permissions=True)
#                 attendance_doc.submit()  # Automatically submit the updated attendance
#                 frappe.db.commit()

#                 if is_early:
#                     frappe.msgprint(f"Early exit logged and submitted for {employee.name}.")
#                 else:
#                     frappe.msgprint(f"Check-out logged and submitted for {employee.name}.")
#             else:
#                 frappe.msgprint(f"Check-out already recorded for {employee.name} today.")
#         else:
#             frappe.log_error(f"No check-in record found for {employee.name}.", "Auto Check-out Error")
#     else:
#         frappe.log_error(f"No employee found for user: {user_email}", "Auto Check-out Error")


# def auto_check_in(login_manager):
#     # Get the logged-in user's email (user_id)
#     user_email = frappe.session.user

#     # Fetch the corresponding Employee record based on user email
#     employee = frappe.db.get_value('Employee', {'user_id': user_email}, ['name', 'attendance_device_id'], as_dict=True)

#     if employee:
#         # Fetch the username from the User document
#         user = frappe.get_doc('User', user_email)
#         username = user.username

#         # Check if attendance_device_id matches the username or email
#         if employee.attendance_device_id == user_email or employee.attendance_device_id == username:
#             # Create an attendance record
#             attendance_exists = frappe.db.exists('Attendance', {
#                 'employee': employee.name,
#                 'attendance_date': nowdate()
#             })

#             if not attendance_exists:
#                 # Create new attendance record
#                 attendance = frappe.get_doc({
#                     'doctype': 'Attendance',
#                     'employee': employee.name,
#                     'attendance_date': nowdate(),
#                     'status': 'Present'
#                 })
#                 attendance.insert(ignore_permissions=True)
#                 frappe.db.commit()
#                 frappe.msgprint(f"Auto Check-In Successful for {employee.name}")
#         else:
#             frappe.msgprint(f"Auto Check-In Failed: Device ID does not match for {employee.name}")
#     else:
#         frappe.msgprint(f"No Employee record found for user: {user_email}")
