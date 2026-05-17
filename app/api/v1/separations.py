from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ...database import get_db
from ..deps import get_current_user
from ...models.user import User
from ...models.separation import Separation
from ...schemas.separation import SeparationCreate, SeparationResponse, ActiveSeparationResponse
from ...services.notification_service import create_notification
from datetime import datetime, date, timedelta

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
def create_separation(request: SeparationCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
        create_notification(
            db, 
            recipient_id=current_user.partner_id, 
            notification_type="separation_started", 
            title=f"{current_user.user_name or 'Your partner'} has started a space", 
            body="You're both in this together."
        )
        
    partner_name = None
    if current_user.partner_id:
        partner = db.query(User).filter(User.id == current_user.partner_id).first()
        if partner:
            partner_name = partner.user_name
            
    # Convert to response
    new_sep.days_elapsed = (date.today() - new_sep.start_date).days
    new_sep.partner_name = partner_name
    return new_sep

@router.get("/active", response_model=ActiveSeparationResponse)
def get_active_separation(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 1. Query where (creator_id = user.id OR partner_id = user.id) AND status = "active"
    sep = db.query(Separation).filter(
        (Separation.creator_id == current_user.id) | (Separation.partner_id == current_user.id),
        Separation.status == "active"
    ).first()
    
    if not sep:
        return ActiveSeparationResponse(is_active=False)
        
    # 2. Compute days_elapsed = (today - start_date).days
    days = (date.today() - sep.start_date).days
    if days < 0:
        days = 0 # in case start_date is in future
        
    # 3. Compute mood_phrase from day number
    # Day 1 is index 1 for the dict. If days elapsed is 0, let's treat it as Day 1.
    day_number = days + 1 
    phrase = MOOD_PHRASES.get(day_number, "Continuing to grow")
    
    partner_name = None
    if current_user.partner_id:
        partner = db.query(User).filter(User.id == current_user.partner_id).first()
        if partner:
            partner_name = partner.user_name
            
    return ActiveSeparationResponse(
        is_active=True,
        days_elapsed=days,
        mood_phrase=phrase,
        partner_name=partner_name
    )

@router.get("/history", response_model=list[SeparationResponse])
def get_separation_history(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    seps = db.query(Separation).filter(
        (Separation.creator_id == current_user.id) | (Separation.partner_id == current_user.id),
        Separation.status == "completed"
    ).order_by(Separation.created_at.desc()).all()
    
    partner = None
    if current_user.partner_id:
        partner = db.query(User).filter(User.id == current_user.partner_id).first()
        
    res = []
    for s in seps:
        s.days_elapsed = (s.ended_at.date() - s.start_date).days if s.ended_at else (date.today() - s.start_date).days
        s.partner_name = (partner.user_name or "Your Partner") if partner else None
        res.append(s)
    return res

@router.get("/{id}", response_model=SeparationResponse)
def get_separation(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sep = db.query(Separation).filter(
        Separation.id == id,
        (Separation.creator_id == current_user.id) | (Separation.partner_id == current_user.id)
    ).first()
    
    if not sep:
        raise HTTPException(status_code=404, detail="Separation not found")
        
    partner = None
    if current_user.partner_id:
        partner = db.query(User).filter(User.id == current_user.partner_id).first()
        
    ended_date = sep.ended_at.date() if sep.ended_at else date.today()
    sep.days_elapsed = (ended_date - sep.start_date).days
    sep.partner_name = (partner.user_name or "Your Partner") if partner else None
    return sep

@router.patch("/{id}/end")
def end_separation(id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sep = db.query(Separation).filter(
        Separation.id == id,
        (Separation.creator_id == current_user.id) | (Separation.partner_id == current_user.id)
    ).first()
    
    if not sep:
        raise HTTPException(status_code=404, detail="Separation not found")
        
    sep.status = "completed"
    sep.ended_at = datetime.utcnow()
    db.commit()
    
    return {"success": True, "message": "Separation ended successfully"}
