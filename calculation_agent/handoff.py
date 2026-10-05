from typing import Any, Optional
from pydantic import BaseModel, Field


class CalculationResult(BaseModel):
    status: str
    operation: str
    policy_id: Optional[str] = None

    current_premium: Optional[float] = None
    proposed_premium: Optional[float] = None

    annual_change: Optional[float] = None
    monthly_change: Optional[float] = None
    percentage_change: Optional[float] = None

    premium_impact: Optional[str] = None

    changed_factors: Optional[Any] = None
    reasons: Optional[Any] = None

    message: Optional[str] = None
    error_message: Optional[str] = None