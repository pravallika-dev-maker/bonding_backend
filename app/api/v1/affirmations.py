import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ...database import get_db
from ...schemas.affirmation import DailyAffirmationResponse
from ...services.affirmation_service import get_or_create_daily_affirmation
from ..deps import get_current_user
from ...models.user import User

router = APIRouter(prefix="/affirmations", tags=["Affirmations"])
logger = logging.getLogger("bonded.api.affirmations")

@router.get("/today", response_model=DailyAffirmationResponse)
async def get_todays_affirmation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        affirmation_obj = await get_or_create_daily_affirmation(db)
        return DailyAffirmationResponse(
            date=affirmation_obj.affirmation_date,
            affirmation=affirmation_obj.affirmation_text
        )
    except Exception as e:
        logger.error(f"Error fetching today's affirmation: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch daily affirmation")
