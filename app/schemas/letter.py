from datetime import datetime
from typing import Optional
from .auth import BaseSchema

class LetterCreate(BaseSchema):
    title: Optional[str] = None
    content: str
    letter_type: Optional[str] = None # No longer required

class LetterResponse(BaseSchema):
    id: int
    title: Optional[str] = None
    content: str
    ai_love_score: int
    is_revealed: bool
    created_at: datetime

    class Config:
        from_attributes = True
