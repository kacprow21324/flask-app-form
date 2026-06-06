VALID_STATUSES = {"draft", "pending", "approved", "rejected"}


def summarize_progress(workflow_rows, total_documents, internship=None, reviewer_role=None):
    counts = {status: 0 for status in VALID_STATUSES}
    pending_for_role = 0

    for row in workflow_rows:
        if row.status not in VALID_STATUSES:
            continue
        counts[row.status] += 1
        if row.status == "pending" and row.reviewer_role == reviewer_role:
            pending_for_role += 1

    started = sum(counts.values())
    total = max(0, int(total_documents or 0))
    approved = counts["approved"]
    hours = max(0, int(getattr(internship, "total_hours", 0) or 0))
    days = max(0, int(getattr(internship, "total_days", 0) or 0))

    return {
        **counts,
        "started": started,
        "approved": approved,
        "total": total,
        "started_percent": round(started / total * 100) if total else 0,
        "approved_percent": round(approved / total * 100) if total else 0,
        "pending_for_role": pending_for_role,
        "hours": hours,
        "days": days,
        "hours_percent": min(100, round(hours / 960 * 100)),
        "days_percent": min(100, round(days / 120 * 100)),
    }
