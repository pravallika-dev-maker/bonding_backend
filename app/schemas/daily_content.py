from pydantic import BaseModel
from datetime import date
from typing import Optional

class DailyAffirmationResponse(BaseModel):
    date: date
    affirmation: str

    class Config:
        from_attributes = True

class DailyInsightResponse(BaseModel):
    date: date
    insight: Optional[str] = None
    is_locked: bool = False
    lock_reason: Optional[str] = None

    class Config:
        from_attributes = True
