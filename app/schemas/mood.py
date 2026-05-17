from datetime import datetime
from typing import Optional
from .auth import BaseSchema

class MoodCreate(BaseSchema):
    mood: str
    reflection: Optional[str] = None

class MoodResponse(BaseSchema):
    id: int
    mood: str
    reflection: Optional[str] = None
    createdAt: datetime

    class Config:
        from_attributes = True
