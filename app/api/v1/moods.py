from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ...database import get_db
from ...schemas.mood import MoodCreate, MoodResponse
from ...models.mood import Mood
from ..deps import get_current_user
from ...models.user import User

router = APIRouter(prefix="/moods", tags=["moods"])

@router.post("/", response_model=MoodResponse)
async def create_mood(
    mood_data: MoodCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_mood = Mood(
        user_id=current_user.id,
        mood=mood_data.mood,
        reflection=mood_data.reflection
    )
    db.add(new_mood)
    db.commit()
    db.refresh(new_mood)
    return new_mood

@router.get("/", response_model=List[MoodResponse])
async def get_my_moods(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    moods = db.query(Mood).filter(Mood.user_id == current_user.id).order_by(Mood.created_at.desc()).all()
    return moods
