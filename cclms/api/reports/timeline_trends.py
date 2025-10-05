import frappe

@frappe.whitelist()
def get_timeline_trends(state="Signed", by="month", months=6, branch=None, company=None, executive_name=None):
    """
    Returns timeseries count for a workflow_state. by=month|week|day.
    For simplicity, we'll do month buckets via DATE_FORMAT in SQL.
    """
    conditions = ["workflow_state = %(state)s"]
    params = {"state": state}

    if branch:
        conditions.append("branch = %(branch)s")
        params["branch"] = branch
    if company:
        conditions.append("company = %(company)s")
        params["company"] = company
    if executive_name:
        conditions.append("executive_name = %(executive_name)s")
        params["executive_name"] = executive_name

    # Use creation date for trend (or post_date if you prefer)
    sql = f"""
        SELECT DATE_FORMAT(creation, '%Y-%m') AS bucket, COUNT(name) AS total
        FROM `tabATM Leads`
        WHERE {' AND '.join(conditions)}
        GROUP BY bucket
        ORDER BY bucket DESC
        LIMIT {int(months)}
    """
    rows = frappe.db.sql(sql, params=params, as_dict=True)
    rows.reverse()  # oldest to newest for chart

    return {"state": state, "points": rows}
