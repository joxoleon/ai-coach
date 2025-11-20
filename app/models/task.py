from datetime import date
from sqlalchemy import Column, Integer, String, Date, JSON

from app.core.database import Base


class TodayTask(Base):
    __tablename__ = "today_tasks"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, default=date.today, index=True)
    name = Column(String, nullable=False)
    group = Column(String, nullable=False)
    url = Column(String, nullable=True)
    extra = Column(JSON, nullable=True)
