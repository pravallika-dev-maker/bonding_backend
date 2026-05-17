import random
from sqlalchemy.orm import Session
from ..models.user import User


class AuthService:
    @staticmethod
    def generate_otp() -> str:
        return str(random.randint(100000, 999999))

    @staticmethod
    async def send_sms_otp(phone_number: str, otp: str):
        print(f"[SMS SERVICE] Sending OTP {otp} to {phone_number}")
        # In a real app, this is where you'd call Twilio/MessageBird
        return True

    @staticmethod
    async def verify_otp(db: Session, phone_number: str, country_code: str, otp: str) -> bool:
        # 1. Verification check (Master code '123456' for development)
        if otp != "123456":
            return False
            
        # 2. Check if user exists, if not, create them (Auto-Registration)
        user = db.query(User).filter(User.phone_number == phone_number).first()
        if not user:
            print(f"[AUTH] Creating new user for phone: {phone_number}")
            user = User(
                phone_number=phone_number,
                country_code=country_code,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            print(f"[AUTH] Existing user logged in: {phone_number}")
            
        return True

