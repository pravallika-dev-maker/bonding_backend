from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ...database import get_db
from ..deps import get_current_user
from ...models.user import User
from ...models.invite_code import InviteCode
from ...models.relationship import Relationship
from ...schemas.partner import InviteCodeResponse, JoinRequest, JoinResponse, PartnerMeResponse
from ...services.notification_service import create_notification, create_notification_and_push
from datetime import datetime, timedelta, timezone
import secrets
import logging

logger = logging.getLogger("bonded.api")

router = APIRouter(prefix="/partners", tags=["partners"])

WORD_LIST = [
    'ROSE', 'LUNA', 'NOVA', 'EDEN', 'SAGE', 'IRIS', 'DAWN', 'STAR', 'VEIL', 'MIST',
    'FERN', 'GLOW', 'HAZE', 'JADE', 'LAKE', 'MOON', 'NEST', 'OPAL', 'PINE', 'RAIN',
    'SILK', 'TIDE', 'VINE', 'WAVE', 'AURA', 'BLISS', 'CALM', 'DOVE', 'ECHO', 'HOPE',
    'LARK', 'PETAL', 'BLOOM', 'DUSK', 'EMBER', 'FROST', 'GRACE', 'HAVEN', 'JEWEL', 'LIGHT',
]

@router.get("/invite-code", response_model=InviteCodeResponse)
def get_invite_code(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        # 1. Delete any old unused codes for this user
        db.query(InviteCode).filter(InviteCode.creator_id == current_user.id, InviteCode.is_used == False).delete()
        
        # 2. Pick a random word from list + random digit
        code_str = f"{secrets.choice(WORD_LIST)}-{secrets.randbelow(9000) + 1000}"
        
        # Check uniqueness (extremely rare collision but good practice)
        while db.query(InviteCode).filter(InviteCode.code == code_str).first() is not None:
            code_str = f"{secrets.choice(WORD_LIST)}-{secrets.randbelow(9000) + 1000}"
            
        # 3. Save to invite_codes table
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        new_code = InviteCode(code=code_str, creator_id=current_user.id, expires_at=expires_at)
        db.add(new_code)
        db.commit()
        db.refresh(new_code)
        
        # 4. Return the code + expires_at
        return InviteCodeResponse(code=new_code.code, expires_at=new_code.expires_at, success=True)
    except Exception as e:
        db.rollback()
        logger.error(f"Database error in get_invite_code: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again.")

@router.post("/join", response_model=JoinResponse)
def join_partner(request: JoinRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    code_str = request.code.upper().strip()
    
    try:
        # 1. Find code in invite_codes where is_used=False and expires_at > now
        invite = db.query(InviteCode).filter(
            InviteCode.code == code_str, 
            InviteCode.is_used == False,
            InviteCode.expires_at > datetime.now(timezone.utc)
        ).first()
        
        # 2. If not found -> return 404 "Invalid or expired code"
        if not invite:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired code")
            
        # 3. If creator_id == current_user.id -> return 400 "Cannot join your own code"
        if invite.creator_id == current_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot join your own code")
            
        # Get the creator
        creator = db.query(User).filter(User.id == invite.creator_id).first()
        if not creator:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator not found")

        # 4. Block if the joiner already has an active relationship
        joiner_active_rel = db.query(Relationship).filter(
            (Relationship.user1_id == current_user.id) | (Relationship.user2_id == current_user.id),
            Relationship.status == "active"
        ).first()
        if joiner_active_rel:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have an active partner connection. Please disconnect your current partner before connecting a new one."
            )

        # 5. Block if the creator already has an active relationship
        creator_active_rel = db.query(Relationship).filter(
            (Relationship.user1_id == creator.id) | (Relationship.user2_id == creator.id),
            Relationship.status == "active"
        ).first()
        if creator_active_rel:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The invite creator already has an active partner connection."
            )

            
        # 4. Set current_user.partner_id = code.creator_id
        current_user.partner_id = creator.id

        # 5. Set creator.partner_id = current_user.id
        creator.partner_id = current_user.id

        # 6. Set both users is_partnered = True
        current_user.is_partnered = True
        creator.is_partnered = True

        # 7. Clear stale partner metadata for both users so old relationship
        #    details don't bleed into the new connection.
        current_user.partner_name = None
        current_user.relation_type = None
        current_user.relationship_date = None
        creator.partner_name = None
        creator.relation_type = None
        creator.relationship_date = None
        
        # 7. Mark code is_used = True
        invite.is_used = True
        
        # 8. Create a new active Relationship
        new_rel = Relationship(
            user1_id=current_user.id,
            user2_id=creator.id,
            status="active",
            journey_score=0
        )
        db.add(new_rel)
        
        # 9. Commit DB
        db.commit()
        
        # Notify creator
        create_notification_and_push(
            db,
            recipient_id=creator.id,
            notification_type="partner_joined",
            title=f"{current_user.user_name or 'Your partner'} joined your bond! 💕",
            body="You are now connected.",
            fcm_token=creator.fcm_token
        )

        # 9. Return { success: true, partner_name: creator.user_name or current_user.partner_name }
        return JoinResponse(
            success=True, 
            partner_name=creator.user_name or current_user.partner_name, 
            message="Successfully connected!"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Database error in join_partner: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again.")

@router.get("/me", response_model=PartnerMeResponse)
def get_partner_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.is_partnered or not current_user.partner_id:
        return PartnerMeResponse(is_connected=False)

    partner = db.query(User).filter(User.id == current_user.partner_id).first()
    if not partner:
        return PartnerMeResponse(is_connected=False)

    return PartnerMeResponse(
        is_connected=True,
        partner_id=partner.id,
        partner_name=partner.user_name or current_user.partner_name,
        gender=partner.gender,
        relation_type=partner.relation_type,
        relationship_date=partner.relationship_date,
        relationship_score=partner.relationship_score,
    )

@router.delete("/disconnect")
def disconnect_partner(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.partner_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You do not have a partner connected")
        
    try:
        partner = db.query(User).filter(User.id == current_user.partner_id).first()
        
        # Clear all active partner fields for current user
        current_user.partner_id = None
        current_user.is_partnered = False
        current_user.partner_name = None
        current_user.relation_type = None
        current_user.relationship_date = None
        
        # Archive the active relationship
        active_rel = db.query(Relationship).filter(
            ((Relationship.user1_id == current_user.id) & (Relationship.user2_id == partner.id)) |
            ((Relationship.user1_id == partner.id) & (Relationship.user2_id == current_user.id)),
            Relationship.status == "active"
        ).first()
        
        if active_rel:
            active_rel.status = "archived"
            active_rel.ended_at = datetime.now(timezone.utc)
            # Persist the final journey score
            active_rel.journey_score = current_user.relationship_score or 0
            
            # Also mark any active separations as completed
            active_sep = db.query(Separation).filter(
                Separation.relationship_id == active_rel.id,
                Separation.status == "active"
            ).first()
            if active_sep:
                active_sep.status = "completed"
                active_sep.ended_at = datetime.now(timezone.utc)
        
        if partner:
            # Clear all active partner fields for the other user too
            partner.partner_id = None
            partner.is_partnered = False
            partner.partner_name = None
            partner.relation_type = None
            partner.relationship_date = None
            
            create_notification_and_push(
                db,
                recipient_id=partner.id,
                notification_type="partner_disconnected",
                title="Your bond has been disconnected",
                body=f"{current_user.user_name or 'Your partner'} has disconnected.",
                fcm_token=partner.fcm_token
            )
            
        db.commit()
        return {"success": True, "message": "Successfully disconnected"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Database error in disconnect_partner: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred. Please try again.")
