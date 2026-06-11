from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ...database import get_db
from ..deps import get_current_user, get_active_relationship
from ...models.user import User
from ...models.separation import Separation
from ...schemas.separation import SeparationCreate, SeparationResponse, ActiveSeparationResponse
from ...services.notification_service import create_notification, create_notification_and_push
from datetime import datetime, date, timedelta, timezone

router = APIRouter(prefix="/separations", tags=["Separations"])

MOOD_PHRASES = {
    1: "Finding stillness",
    2: "Learning to breathe",
    3: "Sitting with yourself",
    4: "Quietly growing",
    5: "Beginning to understand",
    6: "Holding space",
    7: "A week of choosing space"
}

@router.post("/", response_model=SeparationResponse)
def create_separation(
    request: SeparationCreate, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db),
    active_rel = Depends(get_active_relationship)
):
    # Create Separation row
    start_d = datetime.fromisoformat(request.start_date.replace('Z', '+00:00')).date()
    
    # Calculate expected end date
    label = request.duration_label.lower()
    days_to_add = 7 # default
    if "week" in label:
        if "2" in label or "two" in label:
            days_to_add = 14
    elif "month" in label:
        days_to_add = 30
        
    expected_end_d = start_d + timedelta(days=days_to_add)
    
    new_sep = Separation(
        creator_id=current_user.id,
        partner_id=current_user.partner_id,
        relationship_id=active_rel.id if active_rel else None,
        duration_label=request.duration_label,
        start_date=start_d,
        expected_end_date=expected_end_d,
        reason=request.reason
    )
    db.add(new_sep)
    db.commit()
    db.refresh(new_sep)
    
    # Notify partner
    if current_user.partner_id:
        partner = db.query(User).filter(User.id == current_user.partner_id).first()
        create_notification_and_push(
            db, 
            recipient_id=current_user.partner_id, 
            notification_type="separation_started", 
            title="🌿 Space has begun", 
            body=f"{current_user.user_name or 'Your partner'} started a separation.",
            fcm_token=partner.fcm_token if partner else None
        )
        
    partner_name = None
    if current_user.partner_id:
        partner = db.query(User).filter(User.id == current_user.partner_id).first()
        if partner:
            partner_name = partner.user_name or current_user.partner_name
            
    # Convert to response — day 1 is the start date itself (1-based, same as reflections)
    new_sep.days_elapsed = (date.today() - new_sep.start_date).days + 1
    new_sep.partner_name = partner_name
    return new_sep

@router.get("/active", response_model=ActiveSeparationResponse)
def get_active_separation(
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db),
    active_rel = Depends(get_active_relationship)
):
    if not active_rel:
        return ActiveSeparationResponse(is_active=False)

    # 1. Query where (creator_id = user.id OR partner_id = user.id) AND status = "active"
    sep = db.query(Separation).filter(
        (Separation.creator_id == current_user.id) | (Separation.partner_id == current_user.id),
        Separation.relationship_id == active_rel.id,
        Separation.status == "active"
    ).first()
    
    if not sep:
        return ActiveSeparationResponse(is_active=False)
        
    # 2. Compute days_elapsed — 1-based so Day 1 = start date, Day 2 = day after, etc.
    #    This is consistent with how reflections.py calculates day_number (elapsed + 1).
    days = (date.today() - sep.start_date).days + 1
    if days < 1:
        days = 1  # guard against future start_date
        
    # 3. Compute mood_phrase from day number
    phrase = MOOD_PHRASES.get(days, "Continuing to grow")
    
    # Resolve partner_name: try live partner record first, then onboarding fallback
    partner_name = current_user.partner_name  # onboarding fallback
    other_user_id = sep.partner_id if sep.creator_id == current_user.id else sep.creator_id
    if other_user_id:
        other_user = db.query(User).filter(User.id == other_user_id).first()
        if other_user and other_user.user_name:
            partner_name = other_user.user_name
            
    return ActiveSeparationResponse(
        is_active=True,
        id=sep.id,
        duration_label=sep.duration_label,
        start_date=sep.start_date,
        expected_end_date=sep.expected_end_date,
        reason=sep.reason,
        days_elapsed=days,
        mood_phrase=phrase,
        partner_name=partner_name
    )

@router.patch("/{id}/end")
def end_separation(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sep = db.query(Separation).filter(
        Separation.id == id,
        (Separation.creator_id == current_user.id) | (Separation.partner_id == current_user.id)
    ).first()
    
    if not sep:
        raise HTTPException(status_code=404, detail="Separation not found")
        
    sep.status = "completed"
    sep.ended_at = datetime.now(timezone.utc)
    db.commit()
    
    partner_to_notify = sep.partner_id if current_user.id == sep.creator_id else sep.creator_id
    if partner_to_notify:
        partner = db.query(User).filter(User.id == partner_to_notify).first()
        create_notification_and_push(
            db,
            recipient_id=partner_to_notify,
            notification_type="separation_ended",
            title="🌅 Space has ended",
            body=f"{current_user.user_name or 'Your partner'} ended the separation.",
            fcm_token=partner.fcm_token if partner else None
        )

    return {"success": True, "message": "Separation ended successfully"}
