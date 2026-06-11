import logging
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...database import get_db
from ...schemas.affirmation import DailyAffirmationResponse
from ...services.affirmation_service import get_personalized_affirmation
from ..deps import get_current_user
from ...models.user import User
from ...models.separation import Separation
from ...models.reflection_session import ReflectionSession
from ...models.reflection_answer import ReflectionAnswer
from ...models.reflection_question import ReflectionQuestion
from ...models.mood import Mood
from ...models.relationship import Relationship

router = APIRouter(prefix="/affirmations", tags=["Affirmations"])
logger = logging.getLogger("bonded.api.affirmations")

@router.get("/today", response_model=DailyAffirmationResponse)
async def get_todays_affirmation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # ── Step 1: Resolve active separation (if any) ────────────────────────
        active_rel = db.query(Relationship).filter(
            (Relationship.user1_id == current_user.id) | (Relationship.user2_id == current_user.id),
            Relationship.status == "active"
        ).first()

        active_sep = None
        if active_rel:
            active_sep = db.query(Separation).filter(
                Separation.relationship_id == active_rel.id,
                Separation.status == "active"
            ).order_by(Separation.created_at.desc()).first()

        # ── Step 2: Check unlock condition ────────────────────────────────────
        # Affirmation is locked until the user completes today's reflection.
        today_completed = False
        if active_sep:
            today_day = (date.today() - active_sep.start_date).days + 1
            today_session = db.query(ReflectionSession).filter(
                ReflectionSession.user_id == current_user.id,
                ReflectionSession.separation_id == active_sep.id,
                ReflectionSession.day_number == today_day,
                ReflectionSession.is_completed == True,
            ).first()
            today_completed = today_session is not None

        if not today_completed:
            # Return locked state — no affirmation text yet
            return DailyAffirmationResponse(
                date=date.today(),
                affirmation=None,
                is_locked=True,
                lock_reason="Complete today's reflection check-in to unlock your daily affirmation."
            )

        # ── Step 3: Gather user context for personalization ───────────────────
        # Recent moods (last 7)
        recent_moods = db.query(Mood).filter(
            Mood.user_id == current_user.id
        ).order_by(Mood.created_at.desc()).limit(7).all()
        mood_list = [
            {"mood": m.mood, "reflection": m.reflection or ""}
            for m in recent_moods
        ]

        # Recent reflection answers (last 5) for emotional tone context
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
                "tone": ans.ai_tone or "neutral",
            }
            for ans, q in recent_answers
        ]

        in_separation = active_sep is not None

        # ── Step 4: Generate personalized affirmation ─────────────────────────
        affirmation_text = await get_personalized_affirmation(
            user_name=current_user.user_name or "Friend",
            mood_history=mood_list,
            reflection_history=reflection_list,
            in_separation=in_separation,
        )

        return DailyAffirmationResponse(
            date=date.today(),
            affirmation=affirmation_text,
            is_locked=False,
            lock_reason=None
        )

    except Exception as e:
        logger.error(f"Error fetching today's affirmation: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch daily affirmation")
