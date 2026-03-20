import frappe
from frappe.utils import flt, now_datetime


def _get_ai_policy():
    if not frappe.db.exists("DocType", "AI Policy"):
        return None
    return frappe.get_single("AI Policy")


def _call_json_endpoint(url, payload, headers=None):
    from frappe.integrations.utils import make_post_request

    return make_post_request(url, json=payload, headers=headers or {})


def _heuristic_local_result(deal, zip_row):
    zip_score = flt((zip_row or {}).get("zip_score"))
    density = flt((zip_row or {}).get("population_density"))
    competitor = flt((zip_row or {}).get("competitor_density") or (zip_row or {}).get("competitor_kiosks"))

    confidence = 0.55
    summary = (
        f"Local heuristic review for {deal.name}: zip_score={zip_score}, "
        f"population_density={density}, competitor_density={competitor}."
    )
    next_action = "Advance outreach" if zip_score >= 60 and competitor <= 4 else "Review manually before operator submission"

    return {
        "provider": "heuristic-local",
        "model": "rule-engine",
        "confidence": confidence,
        "summary": summary,
        "recommended_next_action": next_action,
    }


def _local_llm_result(policy, payload):
    if not policy or not policy.local_llm_endpoint:
        return None

    result = _call_json_endpoint(
        policy.local_llm_endpoint,
        {
            "model": policy.local_llm_model,
            "input": payload,
        },
    )
    if isinstance(result, dict):
        return {
            "provider": "local-llm",
            "model": policy.local_llm_model,
            "confidence": flt(result.get("confidence")),
            "summary": result.get("summary") or frappe.as_json(result),
            "recommended_next_action": result.get("recommended_next_action"),
        }
    return None


def _gemini_result(policy, payload):
    if not policy or int(policy.enable_gemini_fallback or 0) != 1:
        return None
    if not policy.gemini_endpoint or not policy.gemini_api_key:
        return None

    response = _call_json_endpoint(
        policy.gemini_endpoint,
        {"model": policy.gemini_model, "input": payload},
        headers={"Authorization": f"Bearer {policy.get_password('gemini_api_key')}"},
    )
    if isinstance(response, dict):
        return {
            "provider": "gemini",
            "model": policy.gemini_model,
            "confidence": flt(response.get("confidence")),
            "summary": response.get("summary") or frappe.as_json(response),
            "recommended_next_action": response.get("recommended_next_action"),
        }
    return None


def _create_run_log(action_type, status, summary, **kwargs):
    if not frappe.db.exists("DocType", "Ops Run Log"):
        return None

    doc = frappe.get_doc(
        {
            "doctype": "Ops Run Log",
            "action_type": action_type,
            "status": status,
            "requested_by": frappe.session.user,
            "started_on": kwargs.get("started_on") or now_datetime(),
            "finished_on": kwargs.get("finished_on"),
            "batch_offset": kwargs.get("batch_offset"),
            "batch_limit": kwargs.get("batch_limit"),
            "processed_count": kwargs.get("processed_count"),
            "success_count": kwargs.get("success_count"),
            "failed_count": kwargs.get("failed_count"),
            "skipped_count": kwargs.get("skipped_count"),
            "provider": kwargs.get("provider"),
            "model_used": kwargs.get("model_used"),
            "confidence": kwargs.get("confidence"),
            "summary_json": frappe.as_json(summary, indent=2),
            "error_log": kwargs.get("error_log"),
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def run(limit=25, offset=0, force_gemini=0):
    policy = _get_ai_policy()
    if policy and int(policy.enable_ai_enrichment or 0) != 1:
        return {"processed": 0, "updated": 0, "skipped": 0, "reason": "ai_disabled"}

    if policy and int(policy.manual_confirmation_required or 0) == 1 and int(force_gemini or 0) != 1:
        # manual confirmation required only guards Gemini fallback; local enrichment still runs
        pass

    deals = frappe.db.sql(
        """
        SELECT od.name, od.operator_company, od.location, od.status, od.source_atm_lead,
               loc.location_name, loc.zip_code
        FROM `tabOperator Deal` od
        LEFT JOIN `tabBTM Location` loc ON loc.name = od.location
        ORDER BY od.modified ASC
        LIMIT %(offset)s, %(limit)s
        """,
        {"offset": int(offset), "limit": int(limit)},
        as_dict=True,
    )

    updated = 0
    skipped = 0
    details = []
    started_on = now_datetime()

    for deal in deals:
        zip_row = None
        if deal.zip_code:
            zip_row = frappe.db.get_value("Zip Code Analytics", {"zip_code": deal.zip_code}, "*", as_dict=True)

        payload = {
            "deal": deal,
            "zip_analytics": zip_row,
        }

        result = _local_llm_result(policy, payload) or _heuristic_local_result(deal, zip_row)
        threshold = flt(getattr(policy, "local_confidence_threshold", 0.7) if policy else 0.7)

        if result and flt(result.get("confidence")) < threshold and int(force_gemini or 0) == 1:
            gemini = _gemini_result(policy, payload)
            if gemini:
                result = gemini

        if not result:
            skipped += 1
            continue

        values = {
            "ai_summary": result.get("summary"),
            "ai_confidence": result.get("confidence"),
            "ai_last_provider": result.get("provider"),
            "ai_last_model": result.get("model"),
            "ai_last_enriched_on": now_datetime(),
        }
        if result.get("recommended_next_action"):
            values["recommended_next_action"] = result.get("recommended_next_action")

        frappe.db.set_value("Operator Deal", deal.name, values, update_modified=False)
        updated += 1
        details.append({"deal": deal.name, **result})

    frappe.db.commit()
    log_name = _create_run_log(
        action_type="ai_enrichment",
        status="Success",
        summary={"details": details},
        started_on=started_on,
        finished_on=now_datetime(),
        batch_offset=offset,
        batch_limit=limit,
        processed_count=len(deals),
        success_count=updated,
        skipped_count=skipped,
        provider=(details[-1]["provider"] if details else None),
        model_used=(details[-1]["model"] if details else None),
        confidence=(details[-1]["confidence"] if details else None),
    )

    return {
        "processed": len(deals),
        "updated": updated,
        "skipped": skipped,
        "next_offset": int(offset) + len(deals),
        "run_log": log_name,
    }
