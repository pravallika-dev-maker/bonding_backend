from datetime import datetime
from typing import Optional
from pydantic import Field
from .auth import BaseSchema

class InviteCodeResponse(BaseSchema):
    code: str
    expires_at: datetime
    success: bool = True

class JoinRequest(BaseSchema):
    code: str = Field(..., max_length=20)

class JoinResponse(BaseSchema):
    success: bool
    partner_name: Optional[str] = None
    message: str

class PartnerMeResponse(BaseSchema):
    partner_name: Optional[str] = None
    is_connected: bool
