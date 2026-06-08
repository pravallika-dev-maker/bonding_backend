from sqlalchemy import Column, Integer, String, Date, DateTime, func
from ..database import Base

class DailyAffirmation(Base):
    __tablename__ = "daily_affirmations"

    id = Column(Integer, primary_key=True, index=True)
    affirmation_text = Column(String, nullable=False)
    affirmation_date = Column(Date, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    generated_by = Column(String, default="gemini")
