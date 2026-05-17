from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
from sqlalchemy.orm import Session
from ...database import get_db
from ...schemas.user import UserProfileUpdate
from ...models.user import User
from ..deps import get_current_user

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me")
async def get_my_profile(current_user: User = Depends(get_current_user)):
    return {
        "success": True,
        "data": {
            "id": current_user.id,
            "phoneNumber": current_user.phone_number,
            "userName": current_user.user_name,
            "relationType": current_user.relation_type,
            "partnerName": current_user.partner_name,
            "relationshipDate": current_user.relationship_date.isoformat() if current_user.relationship_date else None,
            "dob": current_user.dob.isoformat() if current_user.dob else None,
            "gender": current_user.gender,
        }
    }

@router.patch("/profile")
async def update_profile(
    profile_data: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    print(f"--- INCOMING PROFILE DATA: {profile_data.model_dump()} ---")
    # Update fields if provided
    if profile_data.userName is not None:
        current_user.user_name = profile_data.userName
    if profile_data.relationType is not None:
        current_user.relation_type = profile_data.relationType
    if profile_data.partnerName is not None:
        current_user.partner_name = profile_data.partnerName
    if profile_data.gender is not None:
        current_user.gender = profile_data.gender
    
    if profile_data.relationshipDate is not None:
        try:
            current_user.relationship_date = datetime.strptime(profile_data.relationshipDate, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid relationshipDate format. Use YYYY-MM-DD")
            
    if profile_data.dob is not None:
        try:
            current_user.dob = datetime.strptime(profile_data.dob, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid dob format. Use YYYY-MM-DD")
        
    db.commit()
    db.refresh(current_user)
    
    return {"message": "Profile updated successfully", "success": True}
