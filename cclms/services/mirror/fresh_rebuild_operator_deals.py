import frappe
def run(
    cutoff_date: str,
    limit: int = 200,
    offset: int = 0,
    commit_every: int = 200,
    stop_on_error: int = 0,
):
    if not cutoff_date:
        frappe.throw("cutoff_date is required")

    from cclms.services.mirror.operator_deal_sync import rebuild_from_cutoff

    return rebuild_from_cutoff(
        cutoff_date=cutoff_date,
        limit=limit,
        offset=offset,
        commit_every=commit_every,
        stop_on_error=stop_on_error,
    )
