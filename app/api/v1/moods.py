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
    # 1. Save the mood to DB
    new_mood = Mood(
        user_id=current_user.id,
        mood=mood_data.mood,
        reflection=mood_data.reflection
    )
    db.add(new_mood)
    db.commit()
    db.refresh(new_mood)

    # 2. Call Gemini AI to generate a personalized quote + advice
    ai_result = await generate_mood_insight(
        mood=mood_data.mood,
        reflection=mood_data.reflection or ""
    )

    # 3. Return mood + AI insight together
    # We return a dict because the Mood ORM model doesn't have ai_quote/ai_advice columns
    return {
        "id": new_mood.id,
        "mood": new_mood.mood,
        "reflection": new_mood.reflection,
        "created_at": new_mood.created_at,
        "ai_quote": ai_result.get("quote"),
        "ai_advice": ai_result.get("advice"),
    }

@router.get("/", response_model=List[MoodResponse])
async def get_my_moods(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    moods = db.query(Mood).filter(Mood.user_id == current_user.id).order_by(Mood.created_at.desc()).all()
    # GET returns historical moods — no AI fields (they were only generated on creation)
    return [
        {
            "id": m.id,
            "mood": m.mood,
            "reflection": m.reflection,
            "created_at": m.created_at,
            "ai_quote": None,
            "ai_advice": None,
        }
        for m in moods
    ]
