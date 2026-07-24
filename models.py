from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    line_user_id = Column(String(255), unique=True, index=True, nullable=False)
    nickname = Column(String(100), nullable=True)
    chat_state = Column(String(50), default="IDLE", nullable=False)
    
    # Times are stored as HH:MM strings (e.g., "21:00") to avoid SQLite/Postgres TIME representation discrepancies.
    notification_time = Column(String(5), default="21:00", nullable=False)
    report_day_of_week = Column(Integer, default=0, nullable=False)  # 0 = Monday, 6 = Sunday
    report_time = Column(String(5), default="09:00", nullable=False)
    
    timezone = Column(String(50), default="Asia/Tokyo", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    entries = relationship("DailyEntry", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("WeeklyReport", back_populates="user", cascade="all, delete-orphan")

class DailyEntry(Base):
    __tablename__ = "daily_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, index=True, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="entries")
    extra_answers = relationship("ExtraAnswer", back_populates="entry", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_date"),
    )

class ExtraAnswer(Base):
    __tablename__ = "extra_answers"

    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(Integer, ForeignKey("daily_entries.id", ondelete="CASCADE"), nullable=False)
    question_key = Column(String(50), nullable=False)  # e.g., "food", "effort", "failed", "tomorrow"
    answer = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    entry = relationship("DailyEntry", back_populates="extra_answers")

    __table_args__ = (
        UniqueConstraint("entry_id", "question_key", name="uq_entry_question"),
    )

class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    report_content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="reports")
