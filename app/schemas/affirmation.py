from pydantic import BaseModel
from datetime import date
from typing import Optional

class DailyAffirmationResponse(BaseModel):
    date: date
    affirmation: Optional[str] = None
    is_locked: bool = False
    lock_reason: Optional[str] = None

    class Config:
        from_attributes = True
