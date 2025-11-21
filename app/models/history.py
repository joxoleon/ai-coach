from datetime import date, datetime
from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class TaskHistory(Base):
    __tablename__ = "task_history"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, default=date.today, index=True)
    module_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    group = Column(String, nullable=False)
    task_type = Column(String, nullable=False, default="todo")
    problem_text = Column(Text, nullable=True)
    code_template = Column(Text, nullable=True)
    log = Column(Text, nullable=True)
    completed = Column(Boolean, default=False)
    difficulty = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
