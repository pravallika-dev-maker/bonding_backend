from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from ...database import get_db
from ...schemas.mood import MoodCreate, MoodResponse
from ...models.mood import Mood
from ..deps import get_current_user
from ...models.user import User
from ...services.ai_service import generate_mood_insight

router = APIRouter(prefix="/moods", tags=["moods"])

@router.post("/", response_model=MoodResponse)
async def create_mood(
    mood_data: MoodCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Call Gemini AI first to generate the personalized quote + advice
    ai_result = await generate_mood_insight(
        mood=mood_data.mood,
        reflection=mood_data.reflection or ""
    )

    # 2. Save the mood + AI output to DB together
    new_mood = Mood(
        user_id=current_user.id,
        mood=mood_data.mood,
        reflection=mood_data.reflection,
        ai_quote=ai_result.get("quote"),
        ai_advice=ai_result.get("advice"),
    )
    db.add(new_mood)
    db.commit()
    db.refresh(new_mood)

    # 3. Return mood with persisted AI insight
    return {
        "id": new_mood.id,
        "mood": new_mood.mood,
        "reflection": new_mood.reflection,
        "created_at": new_mood.created_at,
        "ai_quote": new_mood.ai_quote,
        "ai_advice": new_mood.ai_advice,
    }

@router.get("/", response_model=List[MoodResponse])
async def get_my_moods(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    moods = db.query(Mood).filter(Mood.user_id == current_user.id).order_by(Mood.created_at.desc()).all()
    # Return historical moods with persisted AI fields from DB
    return [
        {
            "id": m.id,
            "mood": m.mood,
            "reflection": m.reflection,
            "created_at": m.created_at,
            "ai_quote": m.ai_quote,
            "ai_advice": m.ai_advice,
        }
        for m in moods
    ]
