from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime

class RelationshipHistoryItem(BaseModel):
    relationship_id: int
    partner_name: Optional[str]
    status: str
    journey_score: int
    separation_count: int
    ended_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class RelationshipSummaryResponse(BaseModel):
    relationship_id: int
    partner_name: Optional[str]
    journey_score: int
    separation_count: int
    relationship_duration_days: int
    status: str
