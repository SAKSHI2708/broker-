from typing import Literal
from pydantic import BaseModel


class TaskHandoffResult(BaseModel):
    action: Literal["SWITCH", "DONE", "RESET"]
    next_agent: Literal["BUY", "UPDATE", "CLAIM", "NONE"]
    message: str