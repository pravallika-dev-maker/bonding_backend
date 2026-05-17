from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from ...schemas.auth import SendCodeRequest, VerifyCodeRequest, TokenResponse
from ...services.auth_service import AuthService
from ...database import get_db
from ...core import security


router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/send-code")
async def send_code(request: SendCodeRequest):
    otp = AuthService.generate_otp()
    await AuthService.send_sms_otp(request.phone_number, otp)
    return {"message": "Code sent successfully", "success": True}

@router.post("/verify-code", response_model=TokenResponse)
async def verify_code(request: VerifyCodeRequest, db: Session = Depends(get_db)):
    is_valid = await AuthService.verify_otp(
        db, 
        request.phone_number, 
        request.country_code, 
        request.otp
    )
    
    if is_valid:
        # Generate real JWT token
        token = security.create_access_token(subject=request.phone_number)
        return {
            "accessToken": token,
            "tokenType": "bearer",
            "success": True
        }
        
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid verification code"
    )


