"""Notification endpoints for the Control Room."""
from fastapi import APIRouter, Query, Request

router = APIRouter()


@router.get("/")
async def list_notifications(
    request: Request,
    type: str = None,
    severity: str = None,
    unread_only: bool = False,
    ticker: str = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    """List notifications with optional filters."""
    pool = request.app.state.db_pool
    conditions = []
    params = []
    idx = 1

    if type:
        conditions.append(f"type = ${idx}")
        params.append(type)
        idx += 1
    if severity:
        conditions.append(f"severity = ${idx}")
        params.append(severity)
        idx += 1
    if unread_only:
        conditions.append("read = FALSE")
    if ticker:
        conditions.append(f"ticker = ${idx}")
        params.append(ticker.upper())
        idx += 1

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    params.extend([limit, offset])
    rows = await pool.fetch(
        f"""
        SELECT id, type, severity, title, body, metadata, ticker, read, created_at
        FROM notifications
        {where}
        ORDER BY created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
    )
    return {
        "count": len(rows),
        "notifications": [
            {
                "id": r["id"],
                "type": r["type"],
                "severity": r["severity"],
                "title": r["title"],
                "body": r["body"],
                "metadata": r["metadata"],
                "ticker": r["ticker"],
                "read": r["read"],
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ],
    }


@router.get("/unread")
async def unread_count(request: Request):
    """Count of unread notifications by severity."""
    pool = request.app.state.db_pool
    rows = await pool.fetch(
        """
        SELECT severity, COUNT(*) as count
        FROM notifications
        WHERE read = FALSE
        GROUP BY severity
        """,
    )
    total = sum(r["count"] for r in rows)
    by_severity = {r["severity"]: r["count"] for r in rows}
    return {"total": total, "by_severity": by_severity}


@router.put("/{notification_id}/read")
async def mark_read(notification_id: int, request: Request):
    """Mark a notification as read."""
    pool = request.app.state.db_pool
    await pool.execute(
        "UPDATE notifications SET read = TRUE WHERE id = $1",
        notification_id,
    )
    return {"id": notification_id, "read": True}


@router.put("/read-all")
async def mark_all_read(request: Request):
    """Mark all notifications as read."""
    pool = request.app.state.db_pool
    result = await pool.execute("UPDATE notifications SET read = TRUE WHERE read = FALSE")
    return {"status": "ok", "updated": result}
