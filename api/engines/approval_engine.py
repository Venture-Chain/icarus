"""
CIO approval gate engine.
Queues actions that require human approval.
"""
from enum import Enum


class ApprovalAction(str, Enum):
    DEPLOY_PAPER = "deploy_paper"
    DEPLOY_LIVE = "deploy_live"
    CHANGE_RISK_LIMITS = "change_risk_limits"
    DEACTIVATE_KILL_SWITCH = "deactivate_kill_switch"
    CHANGE_STRATEGY_PARAMS = "change_strategy_params"
    RETIRE_STRATEGY = "retire_strategy"


REQUIRES_APPROVAL = {
    ApprovalAction.DEPLOY_PAPER,
    ApprovalAction.DEPLOY_LIVE,
    ApprovalAction.CHANGE_RISK_LIMITS,
    ApprovalAction.DEACTIVATE_KILL_SWITCH,
    ApprovalAction.CHANGE_STRATEGY_PARAMS,
    ApprovalAction.RETIRE_STRATEGY,
}


class ApprovalEngine:
    def needs_approval(self, action: ApprovalAction) -> bool:
        return action in REQUIRES_APPROVAL

    async def request_approval(self, action: ApprovalAction, description: str, reasoning: str, payload: dict = None):
        """Queue an action for CIO approval."""
        return {"id": 0, "action": action, "status": "pending"}

    async def get_pending(self):
        """Get all pending approvals."""
        return []

    async def decide(self, approval_id: int, status: str, decided_by: str = "CIO"):
        """Record CIO decision."""
        return {"id": approval_id, "status": status}
