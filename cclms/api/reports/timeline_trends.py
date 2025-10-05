import frappe

@frappe.whitelist()
def get_timeline_trends(state="Signed", months=6, branch=None, company=None, executive_name=None):
    conds = ["workflow_state = %(state)s"]
    params = {"state": state}

    if branch:
        conds.append("branch = %(branch)s")
        params["branch"] = branch
    if company:
        conds.append("company = %(company)s")
        params["company"] = company
    if executive_name:
        conds.append("executive_name = %(executive_name)s")
        params["executive_name"] = executive_name

    sql = f"""
        SELECT DATE_FORMAT(creation, '%%Y-%%m') AS bucket, COUNT(name) AS total
        FROM `tabATM Leads`
        WHERE {" AND ".join(conds)}
        GROUP BY bucket
        ORDER BY bucket DESC
        LIMIT {int(months)}
    """
    rows = frappe.db.sql(sql, params=params, as_dict=True)
    rows.reverse()
    return {"state": state, "points": rows}
