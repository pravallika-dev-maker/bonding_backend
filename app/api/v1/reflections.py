import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import date, datetime, timezone

from ...database import get_db
from ..deps import get_current_user
from ...models.user import User
from ...models.separation import Separation
from ...models.relationship import Relationship
from ...models.reflection_question import ReflectionQuestion
from ...models.reflection_session import ReflectionSession
from ...models.reflection_answer import ReflectionAnswer
from ...schemas.reflection import (
    TodayQuestionResponse, QuestionOut,
    AnswerRequest, AnswerResponse, AIReaction,
    TodayStatusResponse,
)
from ...services.ai_service import analyze_answer

router = APIRouter(prefix="/reflections", tags=["Reflections"])
logger = logging.getLogger("bonded.reflections")


# ── Helper: get active separation or raise 404 ───────────────────────────────

def _get_active_separation(user: User, db: Session) -> Separation:
    """
    Resolves the active separation by first finding the user's active relationship,
    then finding the active separation within that relationship.
    This ensures both partners always resolve the SAME separation and never
    accidentally match stale separations from previous relationships.
    """
    # Step 1: find the user's currently active relationship
    active_rel = db.query(Relationship).filter(
        (Relationship.user1_id == user.id) | (Relationship.user2_id == user.id),
        Relationship.status == "active"
    ).first()

    if not active_rel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active relationship found."
        )

    # Step 2: find the active separation scoped to that relationship
    # Order by created_at desc to always get the latest one if multiple exist
    sep = db.query(Separation).filter(
        Separation.relationship_id == active_rel.id,
        Separation.status == "active"
    ).order_by(Separation.created_at.desc()).first()

    if not sep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active separation found. Start a separation first."
        )
    return sep


# ── Helper: compute today's day_number from separation start ─────────────────

def _day_number(user_id: int, sep: Separation, db: Session) -> int:
    completed_reflections = db.query(ReflectionSession).filter(
        ReflectionSession.user_id == user_id,
        ReflectionSession.separation_id == sep.id,
        ReflectionSession.is_completed == True,
    ).count()
    day = completed_reflections + 1
    return min(day, 55)        # Cap at 55


# ── Helper: get or create today's session ────────────────────────────────────

def _get_or_create_session(user_id: int, sep_id: int, day: int, db: Session) -> ReflectionSession:
    session = db.query(ReflectionSession).filter(
        ReflectionSession.user_id == user_id,
        ReflectionSession.separation_id == sep_id,
        ReflectionSession.day_number == day,
    ).first()
    if not session:
        session = ReflectionSession(
            user_id=user_id,
            separation_id=sep_id,
            day_number=day,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


# ────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ────────────────────────────────────────────────────────────────────────────


@router.get("/questions/today", response_model=TodayQuestionResponse)
async def get_today_question(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns today's reflection question and creates (or returns existing)
    session for the current user.
    """
    sep = _get_active_separation(current_user, db)
    day = _day_number(current_user.id, sep, db)

    question = db.query(ReflectionQuestion).filter(
        ReflectionQuestion.day_number == day,
        ReflectionQuestion.is_active == True,
    ).first()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No question found for day {day}. Make sure the database is seeded."
        )

    session = _get_or_create_session(current_user.id, sep.id, day, db)

    # Fetch category name for context
    category_name = None
    if question.category_id:
        from ...models.question_category import QuestionCategory
        cat = db.query(QuestionCategory).filter(
            QuestionCategory.id == question.category_id
        ).first()
        category_name = cat.name if cat else None

    return TodayQuestionResponse(
        session_id=session.id,
        day_number=day,
        question=QuestionOut(
            id=question.id,
            day_number=question.day_number,
            question_type=question.question_type,
            question_text=question.question_text,
            scenario_prefix=question.scenario_prefix,
            hint_text=question.hint_text,
            category_name=category_name,
        ),
    )


@router.post("/answer", response_model=AnswerResponse)
async def submit_answer(
    request: AnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Saves the user's answer, calls Gemini AI to analyze it, marks today's
    reflection as completed, and returns the AI reaction.
    Since there is one question per day, answering automatically completes the session.
    """
    # Validate session belongs to this user
    session = db.query(ReflectionSession).filter(
        ReflectionSession.id == request.session_id,
        ReflectionSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.is_completed:
        raise HTTPException(
            status_code=400,
            detail="You have already submitted your reflection for today."
        )

    # Check if answer already exists for this question in this session
    existing = db.query(ReflectionAnswer).filter(
        ReflectionAnswer.session_id == session.id,
        ReflectionAnswer.question_id == request.question_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="You have already submitted an answer for this reflection question."
        )

    # Fetch question text for AI prompt
    question = db.query(ReflectionQuestion).filter(
        ReflectionQuestion.id == request.question_id
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # ── Call Gemini AI ──────────────────────────────────────────────────────
    ai_result = await analyze_answer(
        question_text=question.question_text,
        user_answer=request.text_answer,
    )

    # ── Persist answer + AI result ──────────────────────────────────────────
    answer = ReflectionAnswer(
        session_id=session.id,
        user_id=current_user.id,
        question_id=request.question_id,
        text_answer=request.text_answer,
        ai_emotion_detected=ai_result.get("emotion_detected", "neutral"),
        ai_tone=ai_result.get("tone", "neutral"),
        ai_reaction_text=ai_result.get("reaction_text", "Thank you for sharing."),
        ai_processed=True,
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)

    # ── Mark session as completed (one question = one day done) ─────────────
    session.is_completed = True
    session.completed_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(f"User {current_user.id} completed reflection session {session.id} for day {session.day_number}")

    return AnswerResponse(
        answer_id=answer.id,
        ai_reaction=AIReaction(
            emotion_detected=answer.ai_emotion_detected,
            tone=answer.ai_tone,
            reaction_text=answer.ai_reaction_text,
        ),
        is_completed=True,
    )


@router.get("/today/status", response_model=TodayStatusResponse)
async def get_today_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns whether the user and their partner have completed today's reflection,
    plus total completed day counts for both. Used by the home screen.
    """
    sep = _get_active_separation(current_user, db)
    day = _day_number(current_user.id, sep, db)

    # Today's completion status for current user
    user_session = db.query(ReflectionSession).filter(
        ReflectionSession.user_id == current_user.id,
        ReflectionSession.separation_id == sep.id,
        ReflectionSession.day_number == day,
    ).first()
    user_completed = bool(user_session and user_session.is_completed)

    # Total completed days for current user in this separation
    user_total_completed = db.query(ReflectionSession).filter(
        ReflectionSession.user_id == current_user.id,
        ReflectionSession.separation_id == sep.id,
        ReflectionSession.is_completed == True,
    ).count()

    # Partner status (partner_id on the separation row is the other user's id)
    partner_completed = False
    partner_total_completed = 0
    shared_days_completed = 0

    partner_user_id = sep.partner_id if sep.creator_id == current_user.id else sep.creator_id
    if partner_user_id:
        partner_session = db.query(ReflectionSession).filter(
            ReflectionSession.user_id == partner_user_id,
            ReflectionSession.separation_id == sep.id,
            ReflectionSession.day_number == day,
        ).first()
        partner_completed = bool(partner_session and partner_session.is_completed)

        partner_total_completed = db.query(ReflectionSession).filter(
            ReflectionSession.user_id == partner_user_id,
            ReflectionSession.separation_id == sep.id,
            ReflectionSession.is_completed == True,
        ).count()

        # Days where BOTH partners completed their reflection in this separation
        user_completed_days = db.query(ReflectionSession.day_number).filter(
            ReflectionSession.user_id == current_user.id,
            ReflectionSession.separation_id == sep.id,
            ReflectionSession.is_completed == True,
        )
        partner_completed_days = db.query(ReflectionSession.day_number).filter(
            ReflectionSession.user_id == partner_user_id,
            ReflectionSession.separation_id == sep.id,
            ReflectionSession.is_completed == True,
        )
        shared_days_completed = user_completed_days.intersect(partner_completed_days).count()

    return TodayStatusResponse(
        day_number=day,
        user_completed=user_completed,
        partner_completed=partner_completed,
        user_total_completed=user_total_completed,
        partner_total_completed=partner_total_completed,
        shared_days_completed=shared_days_completed,
    )
