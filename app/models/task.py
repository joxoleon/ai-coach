from datetime import date
from sqlalchemy import Column, Integer, String, Date, JSON, Text

from app.core.database import Base


class TodayTask(Base):
    __tablename__ = "today_tasks"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, default=date.today, index=True)
    module_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    group = Column(String, nullable=False)
    task_type = Column(String, nullable=False, default="todo")
    problem_text = Column(Text, nullable=True)
    todo_text = Column(Text, nullable=True)
    code_template = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    log = Column(Text, nullable=True)
    url = Column(String, nullable=True)
    extra = Column(JSON, nullable=True)
