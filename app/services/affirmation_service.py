import logging
import datetime
from sqlalchemy.orm import Session
from ..models.daily_affirmation import DailyAffirmation
from .ai_service import generate_daily_affirmation

logger = logging.getLogger("bonded.affirmations")

async def get_or_create_daily_affirmation(db: Session) -> DailyAffirmation:
    today = datetime.date.today()
    
    try:
        # Check if today's affirmation exists
        affirmation = db.query(DailyAffirmation).filter(DailyAffirmation.affirmation_date == today).first()
        if affirmation:
            return affirmation
            
        # If not, generate a new one
        logger.info(f"Generating new affirmation for {today}")
        new_text = await generate_daily_affirmation()
        
        # Save to DB
        new_affirmation = DailyAffirmation(
            affirmation_text=new_text,
            affirmation_date=today,
            generated_by="gemini"
        )
        db.add(new_affirmation)
        db.commit()
        db.refresh(new_affirmation)
        logger.info(f"Successfully saved new affirmation for {today}")
        return new_affirmation
        
    except Exception as e:
        logger.error(f"Error in get_or_create_daily_affirmation: {e}")
        db.rollback()
        # Fallback return in case of DB failure to still serve user
        import random
        fallback_text = random.choice([
            "Love grows stronger when two hearts choose understanding every day.",
            "Every day is a new chance to choose each other."
        ])
        return DailyAffirmation(affirmation_text=fallback_text, affirmation_date=today, generated_by="fallback")
