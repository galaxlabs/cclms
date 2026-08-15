import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate


@frappe.whitelist()
def productivity_overview(from_date=None, to_date=None, branch=None):
    """Aggregate tracker productivity by department/branch, app and rating.

    Reads Employee Activity Log -> activity_logs (Activity Entry) child rows.
    """
    to_date = to_date or nowdate()
    from_date = from_date or add_days(to_date, -6)
    filters = [["date", "between", [from_date, to_date]]]
    if branch:
        filters.append(["sales_agent", "in", _agents_for_branch(branch)])

    logs = frappe.get_all(
        "Employee Activity Log",
        filters=filters,
        fields=["name", "employee", "user", "sales_agent", "date", "total_active_minutes", "total_talk_time", "unauthorized_site_hits", "productivity_score"],
        order_by="date desc",
        limit_page_length=100000,
    )
    if not logs:
        return {"logs": [], "by_branch": [], "by_app": [], "by_rating": {}, "totals": {}}

    # Resolve branch from Sales Agent once
    agent_branch = _sales_agent_branches([l.get("sales_agent") for l in logs])

    by_agent = {}
    for log in logs:
        agent = log.get("sales_agent") or log.get("employee") or log.get("user") or "Unknown"
        entry = by_agent.setdefault(agent, {"agent": agent, "branch": agent_branch.get(agent) or "", "active_minutes": 0, "idle_minutes": 0, "talk_seconds": 0, "unauthorized": 0, "score": 0, "rows": 0})
        entry["active_minutes"] += int(log.get("total_active_minutes") or 0)
        entry["idle_minutes"] += int(log.get("total_idle_minutes") or 0)
        entry["talk_seconds"] += int(log.get("total_talk_time") or 0)
        entry["unauthorized"] += int(log.get("unauthorized_site_hits") or 0)
        entry["score"] += int(log.get("productivity_score") or 0)
        entry["rows"] += 1

    # App / rating rollup from activity entries
    by_app = {}
    by_rating = {}
    total_minutes = 0
    productive_min = 0
    unproductive_min = 0
    for log in logs:
        entries = _activity_entries(log.name)
        for row in entries:
            minutes = int(row.get("event_minutes") or 0)
            total_minutes += minutes
            app = (row.get("active_app") or row.get("domain") or "Unknown").strip() or "Unknown"
            app_bucket = by_app.setdefault(app, {"app": app, "minutes": 0, "productive": 0, "unproductive": 0})
            app_bucket["minutes"] += minutes
            rating = row.get("productivity_rating") or ""
            by_rating[rating] = by_rating.get(rating, 0) + minutes
            if rating == "productive":
                productive_min += minutes
                app_bucket["productive"] += minutes
            elif rating == "unproductive":
                unproductive_min += minutes
                app_bucket["unproductive"] += minutes

    branch_map = {}
    for agent_data in by_agent.values():
        branch = agent_data["branch"] or "Unassigned"
        bucket = branch_map.setdefault(branch, {"branch": branch, "agents": 0, "active_minutes": 0, "idle_minutes": 0, "talk_seconds": 0, "unauthorized": 0, "score": 0})
        bucket["agents"] += 1
        bucket["active_minutes"] += agent_data["active_minutes"]
        bucket["idle_minutes"] += agent_data["idle_minutes"]
        bucket["talk_seconds"] += agent_data["talk_seconds"]
        bucket["unauthorized"] += agent_data["unauthorized"]
        bucket["score"] += agent_data["score"]

    # Net productive time: active minutes minus idle, capped to a 9-hour workday.
    workday_minutes = int(frappe.conf.get("tracker_workday_minutes") or 540)

    return {
        "logs": sorted(by_agent.values(), key=lambda x: x["active_minutes"], reverse=True),
        "by_branch": sorted(branch_map.values(), key=lambda x: x["active_minutes"], reverse=True),
        "by_app": sorted(by_app.values(), key=lambda x: x["minutes"], reverse=True)[:30],
        "by_rating": by_rating,
        "totals": {
            "agents": len(by_agent),
            "total_minutes": total_minutes,
            "productive_minutes": productive_min,
            "unproductive_minutes": unproductive_min,
            "active_minutes": sum(x["active_minutes"] for x in by_agent.values()),
            "idle_minutes": sum(x["idle_minutes"] for x in by_agent.values()),
            "workday_minutes": workday_minutes,
            "talk_seconds": sum(x["talk_seconds"] for x in by_agent.values()),
            "unauthorized": sum(x["unauthorized"] for x in by_agent.values()),
        },
    }


@frappe.whitelist()
def departments():
    """List departments/branches used by sales agents for dashboard filtering."""
    if not frappe.db.exists("DocType", "Sales Agent"):
        return []
    branches = frappe.get_all("Sales Agent", fields=["branch"], distinct=True)
    return sorted({b.get("branch") for b in branches if b.get("branch")})


def _sales_agent_branches(agent_names):
    """Map Sales Agent names -> branch."""
    if not frappe.db.exists("DocType", "Sales Agent"):
        return {}
    result = {}
    for name in set(n for n in agent_names if n):
        branch = frappe.db.get_value("Sales Agent", name, "branch")
        if branch:
            result[name] = branch
    return result


def _agents_for_branch(branch):
    if not frappe.db.exists("DocType", "Sales Agent"):
        return []
    return frappe.get_all("Sales Agent", filters={"branch": branch}, pluck="name")


def _activity_entries(log_name):
    """Return activity entries child rows for a log."""
    try:
        doc = frappe.get_doc("Employee Activity Log", log_name)
        rows = doc.get("activity_logs") or []
        return [r.as_dict() for r in rows]
    except Exception:
        return []
