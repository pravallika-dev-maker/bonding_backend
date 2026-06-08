from pydantic import BaseModel
from datetime import date

class DailyAffirmationResponse(BaseModel):
    date: date
    affirmation: str

    class Config:
        from_attributes = True
