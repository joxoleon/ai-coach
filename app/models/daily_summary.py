from datetime import date
from sqlalchemy import Column, Integer, Date, Text

from app.core.database import Base


class DailySummary(Base):
    __tablename__ = "daily_summary"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, default=date.today, unique=True, index=True)
    summary_text = Column(Text, nullable=True)
    raw_ai_response = Column(Text, nullable=True)
