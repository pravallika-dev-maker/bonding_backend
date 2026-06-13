import logging
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...database import get_db
from ...schemas.home import HomeHeroResponse
from ..deps import get_current_user
from ...models.user import User
from ...models.relationship import Relationship
from ...models.separation import Separation
import random

router = APIRouter(prefix="/home", tags=["Home"])
logger = logging.getLogger("bonded.api.home")

COMFORT_MESSAGES = [
    "Every quiet moment brings deeper clarity.",
    "Growth often happens in the spaces between conversations.",
    "Distance can create room for understanding.",
    "Patience is the quietest form of love.",
    "True connection deepens even when apart.",
    "This time is a gift of self-discovery.",
    "A step back is sometimes a step forward.",
    "Take this day to nourish your own heart.",
    "Understanding blooms in stillness.",
    "Reflection paves the path to healing."
]

@router.get("/hero", response_model=HomeHeroResponse)
async def get_home_hero(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Check if partner is connected via an active relationship
        active_rel = db.query(Relationship).filter(
            (Relationship.user1_id == current_user.id) | (Relationship.user2_id == current_user.id),
            Relationship.status == "active"
        ).first()
        # Check for any past relationships
        has_past = db.query(Relationship).filter(
            (Relationship.user1_id == current_user.id) | (Relationship.user2_id == current_user.id)
        ).first() is not None

        if not active_rel:
            return HomeHeroResponse(
                partner_connected=False,
                partner_name=current_user.partner_name,
                has_past_relationship=has_past
            )

        # Resolve partner name
        partner_id = active_rel.user2_id if active_rel.user1_id == current_user.id else active_rel.user1_id
        partner_name = current_user.partner_name
        if partner_id:
            partner = db.query(User).filter(User.id == partner_id).first()
            if partner and partner.user_name:
                partner_name = partner.user_name

        # Check for active separation
        active_sep = db.query(Separation).filter(
            Separation.relationship_id == active_rel.id,
            Separation.status == "active"
        ).first()

        if not active_sep:
            return HomeHeroResponse(
                partner_connected=True,
                partner_name=partner_name,
                has_past_relationship=has_past
            )

        # Calculate days and progress
        from sqlalchemy import cast, Date
        from ...models.reflection_session import ReflectionSession

        completed_reflections = db.query(ReflectionSession).filter(
            ReflectionSession.user_id == current_user.id,
            ReflectionSession.separation_id == active_sep.id,
            ReflectionSession.is_completed == True,
        ).count()

        active_day = completed_reflections + 1
        calendar_day = (date.today() - active_sep.start_date).days + 1
        if calendar_day < 1:
            calendar_day = 1
            
        current_day = active_day
        total_days = (active_sep.expected_end_date - active_sep.start_date).days
        if total_days <= 0:
            total_days = 1 # Avoid division by zero
            
        progress_percentage = (current_day / total_days) * 100.0
        if progress_percentage > 100.0:
            progress_percentage = 100.0
            
        # ── Get-or-create today's comfort message (persisted, never regenerated) ──
        from ...models.user_daily_comfort import UserDailyComfort
        today = date.today()

        existing_comfort = db.query(UserDailyComfort).filter(
            UserDailyComfort.user_id == current_user.id,
            UserDailyComfort.comfort_date == today
        ).first()

        if existing_comfort:
            # Return the same quote stored for today — no regeneration
            comfort_message = existing_comfort.text
        else:
            # First call today: generate and persist
            comfort_message = random.choice(COMFORT_MESSAGES)
            try:
                from ...services.ai_service import _get_client
                client = _get_client()
                prompt = (
                    "Generate a single, very short comforting message (1 sentence) for someone "
                    "in a relationship separation journey. It should be warm, supportive, and easy "
                    "to understand. Examples: 'Every quiet moment brings deeper clarity.' or "
                    "'Distance can create room for understanding.'"
                )
                response = await client.aio.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                )
                text = response.text.strip().strip('"').strip()
                if text:
                    comfort_message = text
            except Exception as e:
                logger.error(f"Gemini comfort_message generation failed: {e}")

            # Persist so every subsequent call today returns the same quote
            new_comfort = UserDailyComfort(
                user_id=current_user.id,
                comfort_date=today,
                text=comfort_message
            )
            db.add(new_comfort)
            try:
                db.commit()
            except Exception:
                db.rollback()

        # Override comfort_message based on Gentle Sequential Progression rules
        completed_today = db.query(ReflectionSession).filter(
            ReflectionSession.user_id == current_user.id,
            ReflectionSession.separation_id == active_sep.id,
            ReflectionSession.is_completed == True,
            cast(ReflectionSession.completed_at, Date) == today
        ).first() is not None

        if completed_today:
            comfort_message = f"Beautiful reflection ❤️ Day {active_day} is now ready whenever you are."
        elif active_day < calendar_day:
            comfort_message = f"Looks like Day {active_day} is still waiting for you ❤️ No worries. Let's continue from where you left off. Every reflection helps us understand your journey a little better."

        return HomeHeroResponse(
            partner_connected=True,
            partner_name=partner_name,
            current_day=current_day,
            total_duration_days=total_days,
            progress_percentage=round(progress_percentage, 2),
            comfort_message=comfort_message,
            has_past_relationship=has_past
        )

    except Exception as e:
        logger.error(f"Error fetching home hero: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch home hero data")
