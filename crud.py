from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import date, datetime
import models
import schemas
from typing import List, Optional

def get_user(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_line_id(db: Session, line_user_id: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.line_user_id == line_user_id).first()

def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    db_user = models.User(
        line_user_id=user.line_user_id,
        nickname=user.nickname,
        notification_time=user.notification_time,
        report_day_of_week=user.report_day_of_week,
        report_time=user.report_time,
        timezone=user.timezone,
        chat_state="IDLE"
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_id: int, user_update: schemas.UserUpdate) -> Optional[models.User]:
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    
    update_data = user_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

def get_daily_entry_by_date(db: Session, user_id: int, entry_date: date) -> Optional[models.DailyEntry]:
    return db.query(models.DailyEntry).filter(
        and_(models.DailyEntry.user_id == user_id, models.DailyEntry.date == entry_date)
    ).first()

def create_or_update_daily_entry(db: Session, user_id: int, entry_date: date, content: str) -> models.DailyEntry:
    db_entry = get_daily_entry_by_date(db, user_id, entry_date)
    if db_entry:
        db_entry.content = content
        db_entry.created_at = datetime.utcnow()
    else:
        db_entry = models.DailyEntry(
            user_id=user_id,
            date=entry_date,
            content=content
        )
        db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry

def create_or_update_extra_answer(db: Session, entry_id: int, question_key: str, answer: str) -> models.ExtraAnswer:
    db_answer = db.query(models.ExtraAnswer).filter(
        and_(models.ExtraAnswer.entry_id == entry_id, models.ExtraAnswer.question_key == question_key)
    ).first()
    
    if db_answer:
        db_answer.answer = answer
        db_answer.created_at = datetime.utcnow()
    else:
        db_answer = models.ExtraAnswer(
            entry_id=entry_id,
            question_key=question_key,
            answer=answer
        )
        db.add(db_answer)
    db.commit()
    db.refresh(db_answer)
    return db_answer

def create_weekly_report(db: Session, user_id: int, start_date: date, end_date: date, content: str) -> models.WeeklyReport:
    db_report = models.WeeklyReport(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        report_content=content
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

def get_users_to_notify(db: Session, time_str: str) -> List[models.User]:
    # Find all active users whose notification_time matches the given HH:MM
    return db.query(models.User).filter(
        and_(
            models.User.is_active == True,
            models.User.notification_time == time_str
        )
    ).all()

def get_users_for_weekly_report(db: Session, day_of_week: int, time_str: str) -> List[models.User]:
    # Find active users whose report day and time matches
    return db.query(models.User).filter(
        and_(
            models.User.is_active == True,
            models.User.report_day_of_week == day_of_week,
            models.User.report_time == time_str
        )
    ).all()

def get_recent_entries_with_answers(db: Session, user_id: int, start_date: date, end_date: date) -> List[models.DailyEntry]:
    return db.query(models.DailyEntry).filter(
        and_(
            models.DailyEntry.user_id == user_id,
            models.DailyEntry.date >= start_date,
            models.DailyEntry.date <= end_date
        )
    ).order_by(models.DailyEntry.date.asc()).all()
