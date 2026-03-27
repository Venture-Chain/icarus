from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

router = APIRouter()

# Connected WebSocket clients for real-time updates
connected_clients: list[WebSocket] = []


class ApprovalDecision(BaseModel):
    status: str  # approved, rejected
    decided_by: str = "CIO"
    reason: str = ""


class ApprovalRequest(BaseModel):
    action_type: str
    description: str
    reasoning: str = ""
    payload: dict = {}


@router.get("/")
async def list_pending_approvals():
    """List all pending CIO approvals."""
    return {"approvals": []}


@router.get("/{approval_id}")
async def get_approval(approval_id: int):
    """Get approval details with reasoning."""
    return {"id": approval_id}


@router.post("/")
async def create_approval(request: ApprovalRequest):
    """Create a new approval request (called by engines)."""
    for client in connected_clients:
        try:
            await client.send_json({
                "type": "new_approval",
                "action": request.action_type,
                "description": request.description,
            })
        except Exception:
            pass
    return {"id": 0, "status": "pending"}


@router.put("/{approval_id}")
async def decide_approval(approval_id: int, decision: ApprovalDecision):
    """Approve or reject a pending action."""
    for client in connected_clients:
        try:
            await client.send_json({
                "type": "approval_decided",
                "id": approval_id,
                "status": decision.status,
            })
        except Exception:
            pass
    return {"id": approval_id, "status": decision.status}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time approval notifications."""
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
