import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime, getdate, flt


def _resolve_sales_agent():
    user = frappe.session.user
    if not user or user == "Guest":
        return None
    if frappe.db.exists("DocType", "Sales Agent"):
        # user permission first
        rows = frappe.get_all("User Permission", filters={"user": user, "allow": "Sales Agent"}, fields=["for_value"], limit=1)
        if rows:
            return rows[0]["for_value"]
        agent = frappe.db.get_value("Sales Agent", {"user": user}, "name")
        if agent:
            return agent
    return None


def _followup_stats(agent, from_date, to_date):
    """Follow-up counts: scheduled, due, completed, missed, today due, completion rate."""
    today = getdate()
    base = [["assigned_to", "=", agent]] if agent else []
    total = frappe.db.count("Follow-up Schedule", base)
    due = frappe.db.count("Follow-up Schedule", base + [["status", "in", ["Scheduled", "Due"]], ["follow_up_time", "<=", add_to_date(now_datetime(), minutes=5)]])
    scheduled = frappe.db.count("Follow-up Schedule", base + [["status", "=", "Scheduled"]])
    completed = frappe.db.count("Follow-up Schedule", base + [["status", "=", "Completed"]])
    missed = frappe.db.count("Follow-up Schedule", base + [["status", "=", "Missed"]])
    today_due = frappe.db.count("Follow-up Schedule", base + [["follow_up_time", "between", [str(today) + " 00:00:00", str(today) + " 23:59:59"]], ["status", "in", ["Scheduled", "Due"]]])
    rate = round(completed / total * 100, 1) if total else 0
    return {
        "total": total, "scheduled": scheduled, "due": due,
        "completed": completed, "missed": missed, "today_due": today_due,
        "completion_rate": rate,
    }


def _hrms_stats(from_date, to_date):
    """Attendance counts within the range."""
    present = frappe.db.count("Attendance", [["attendance_date", "between", [from_date, to_date]], ["status", "=", "Present"], ["docstatus", "=", 1]])
    absent = frappe.db.count("Attendance", [["attendance_date", "between", [from_date, to_date]], ["status", "=", "Absent"], ["docstatus", "=", 1]])
    on_leave = frappe.db.count("Attendance", [["attendance_date", "between", [from_date, to_date]], ["status", "=", "On Leave"], ["docstatus", "=", 1]])
    employees = frappe.db.count("Employee", [["status", "=", "Active"]])
    return {"present": present, "absent": absent, "on_leave": on_leave, "active_employees": employees}


def _activity_stats(agent, from_date, to_date):
    """Productivity / activity rollups from Employee Activity Log."""
    filters = [["date", "between", [from_date, to_date]]]
    if agent:
        filters.append(["sales_agent", "=", agent])
    logs = frappe.get_all(
        "Employee Activity Log",
        filters=filters,
        fields=["total_active_minutes", "total_idle_minutes", "unauthorized_site_hits", "productivity_score", "total_calls_today"],
    )
    active = sum(flt(r.get("total_active_minutes") or 0) for r in logs)
    idle = sum(flt(r.get("total_idle_minutes") or 0) for r in logs)
    hits = sum(int(r.get("unauthorized_site_hits") or 0) for r in logs)
    scores = [flt(r.get("productivity_score") or 0) for r in logs if r.get("productivity_score")]
    calls = sum(int(r.get("total_calls_today") or 0) for r in logs)
    workday_minutes = 540  # 9h tracker workday
    net = min(workday_minutes * max(len(logs), 1), max(active - idle, 0))
    return {
        "active_minutes": round(active, 1),
        "idle_minutes": round(idle, 1),
        "unauthorized_hits": hits,
        "avg_productivity": round(sum(scores) / len(scores), 1) if scores else 0,
        "tracked_calls": calls,
        "active_hours": round(net / 60, 1),
        "log_days": len(logs),
    }


def _call_stats(from_date, to_date):
    """Call Detail rollups + Call Daily Summary daily targets."""
    calls = frappe.db.count("Call Detail", [["call_date", "between", [from_date, to_date]]])
    answered = frappe.db.count("Call Detail", [["call_date", "between", [from_date, to_date]], ["status", "in", ["Answered", "Talked", "Completed"]]])
    missed = frappe.db.count("Call Detail", [["call_date", "between", [from_date, to_date]], ["status", "in", ["Missed", "Not Answered", "No Answer"]]])
    talk_seconds = flt(frappe.db.sql("SELECT COALESCE(SUM(talk_duration_seconds),0) FROM `tabCall Detail` WHERE call_date BETWEEN %s AND %s", (from_date, to_date))[0][0] or 0)

    # Daily targets from Call Daily Summary (total_calls vs a 20-call target per day)
    cds = frappe.get_all(
        "Call Daily Summary",
        filters=[["date", "between", [from_date, to_date]]],
        fields=["date", "total_calls", "answered_calls", "status"],
        order_by="date asc",
    )
    days = {}
    for r in cds:
        d = str(r.get("date"))
        if d not in days:
            days[d] = {"date": d, "total_calls": 0, "answered": 0}
        days[d]["total_calls"] += int(r.get("total_calls") or 0)
        days[d]["answered"] += int(r.get("answered_calls") or 0)
    target_per_day = 20
    daily = []
    for d, v in sorted(days.items()):
        met = v["total_calls"] >= target_per_day
        daily.append({**v, "target": target_per_day, "met": met})
    met_days = sum(1 for v in daily if v["met"])

    return {
        "total_calls": calls,
        "answered": answered,
        "missed": missed,
        "talk_seconds": round(talk_seconds),
        "talk_minutes": round(talk_seconds / 60, 1),
        "daily_target": target_per_day,
        "met_days": met_days,
        "days": daily,
    }


@frappe.whitelist()
def dashboard_stats(from_date=None, to_date=None):
    """Combined stats for the unified XG Hub dashboard."""
    to_date = to_date or str(getdate())
    from_date = from_date or str(add_to_date(getdate(), days=-29))
    agent = _resolve_sales_agent()
    return {
        "followups": _followup_stats(agent, from_date, to_date),
        "hrms": _hrms_stats(from_date, to_date),
        "activity": _activity_stats(agent, from_date, to_date),
        "calls": _call_stats(from_date, to_date),
        "sales_agent": agent,
    }
