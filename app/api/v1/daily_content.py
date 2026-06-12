import logging
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...database import get_db
from ...schemas.daily_content import DailyAffirmationResponse, DailyInsightResponse
from ...services.daily_content_service import get_or_create_daily_affirmation, get_or_create_daily_insight
from ..deps import get_current_user
from ...models.user import User
from ...models.separation import Separation
from ...models.relationship import Relationship
from ...models.mood import Mood
from ...models.reflection_answer import ReflectionAnswer
from ...models.reflection_question import ReflectionQuestion

router = APIRouter(prefix="/daily", tags=["Daily Content"])
logger = logging.getLogger("bonded.api.daily_content")

@router.get("/affirmation", response_model=DailyAffirmationResponse)
async def get_daily_affirmation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Determine if there is an active separation
        active_rel = db.query(Relationship).filter(
            (Relationship.user1_id == current_user.id) | (Relationship.user2_id == current_user.id),
            Relationship.status == "active"
        ).first()

        in_separation = False
        if active_rel:
            active_sep = db.query(Separation).filter(
                Separation.relationship_id == active_rel.id,
                Separation.status == "active"
            ).first()
            in_separation = active_sep is not None

        affirmation_text = await get_or_create_daily_affirmation(
            db=db,
            current_user=current_user,
            in_separation=in_separation
        )

        return DailyAffirmationResponse(
            date=date.today(),
            affirmation=affirmation_text
        )

    except Exception as e:
        logger.error(f"Error fetching daily affirmation: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch daily affirmation")


@router.get("/insight", response_model=DailyInsightResponse)
async def get_daily_insight(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # 1. Check if user has a partner
        if not current_user.partner_id:
            return DailyInsightResponse(
                date=date.today(),
                insight=None,
                is_locked=True,
                lock_reason="Connect with a partner to begin your reflection journey and unlock daily insights."
            )

        # 2. Check Unlock Condition (Mood logged today)
        today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
        
        mood_today = db.query(Mood).filter(
            Mood.user_id == current_user.id,
            Mood.created_at >= today_start
        ).first()
        
        if not mood_today:
            return DailyInsightResponse(
                date=date.today(),
                insight=None,
                is_locked=True,
                lock_reason="Complete today's mood check-in to unlock your daily relationship insight."
            )

        # 2. Gather context
        recent_moods = db.query(Mood).filter(
            Mood.user_id == current_user.id
        ).order_by(Mood.created_at.desc()).limit(7).all()
        mood_list = [
            {"mood": m.mood, "reflection": m.reflection or ""}
            for m in recent_moods
        ]

        recent_answers = db.query(ReflectionAnswer, ReflectionQuestion).join(
            ReflectionQuestion, ReflectionAnswer.question_id == ReflectionQuestion.id
        ).filter(
            ReflectionAnswer.user_id == current_user.id
        ).order_by(ReflectionAnswer.id.desc()).limit(5).all()
        reflection_list = [
            {
                "question": q.question_text,
                "answer": ans.text_answer,
                "emotion": ans.ai_emotion_detected or "neutral",
            }
            for ans, q in recent_answers
        ]

        # 3. Generate or retrieve today's insight
        insight_text = await get_or_create_daily_insight(
            db=db,
            current_user=current_user,
            mood_history=mood_list,
            reflection_history=reflection_list
        )

        return DailyInsightResponse(
            date=date.today(),
            insight=insight_text,
            is_locked=False,
            lock_reason=None
        )

    except Exception as e:
        logger.error(f"Error fetching daily insight: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch daily insight")
