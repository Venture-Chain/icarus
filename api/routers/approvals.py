from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ApprovalDecision(BaseModel):
    status: str  # approved, rejected
    decided_by: str = "CIO"
    reason: str = ""


@router.get("/")
async def list_pending_approvals():
    """List all pending CIO approvals."""
    return {"approvals": []}


@router.get("/{approval_id}")
async def get_approval(approval_id: int):
    """Get approval details."""
    return {"id": approval_id}


@router.put("/{approval_id}")
async def decide_approval(approval_id: int, decision: ApprovalDecision):
    """Approve or reject a pending action."""
    return {"id": approval_id, "status": decision.status}
