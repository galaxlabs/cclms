def run(limit: int = 0, commit_every: int = 200, overwrite: int = 0):
    frappe.flags.maintenance_mode = True

    from cclms.services.mirror.operator_deal_sync import backfill_dates

    return backfill_dates(
        limit=limit,
        offset=0,
        commit_every=commit_every,
        overwrite=overwrite,
    )
