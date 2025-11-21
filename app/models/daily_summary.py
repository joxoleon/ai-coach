from datetime import date
from sqlalchemy import Column, Integer, Date, Text, String, UniqueConstraint

from app.core.database import Base


class DailySummary(Base):
    __tablename__ = "daily_summary"
    __table_args__ = (UniqueConstraint("date", "module_id", name="uq_daily_summary_date_module"),)

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, default=date.today, index=True)
    module_id = Column(String, nullable=False, index=True)
    summary_text = Column(Text, nullable=True)
    raw_ai_response = Column(Text, nullable=True)
