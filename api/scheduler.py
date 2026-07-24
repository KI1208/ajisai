from fastapi import APIRouter, Depends, HTTPException, status, Security
from fastapi.security.api_key import APIKeyHeader, APIKeyQuery
from sqlalchemy.orm import Session
from sqlalchemy import and_
import datetime
from zoneinfo import ZoneInfo
from typing import List

from config import settings
from database import get_db
import models
import crud
from services.line_service import send_daily_question, push_text, QUESTIONS
from services.gemini_service import generate_weekly_report

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])

api_key_header = APIKeyHeader(name="X-Scheduler-Key", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)

def verify_scheduler_key(
    key_header: str = Security(api_key_header),
    key_query: str = Security(api_key_query)
):
    expected_key = settings.SCHEDULER_API_KEY
    if key_header == expected_key or key_query == expected_key:
        return True
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized scheduler trigger"
    )

def get_now_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)

@router.post("/check-triggers", dependencies=[Depends(verify_scheduler_key)])
def check_triggers(db: Session = Depends(get_db)):
    """
    Main polling endpoint called by Cloud Scheduler (e.g., every minute or every 5 minutes).
    Checks if there are daily notifications or weekly reports due for any user.
    """
    utc_now = get_now_utc()
    active_users = db.query(models.User).filter(models.User.is_active == True).all()
    
    daily_notifications_sent = 0
    weekly_reports_sent = 0
    
    for user in active_users:
        try:
            tz = ZoneInfo(user.timezone)
        except Exception:
            tz = ZoneInfo("Asia/Tokyo")
            
        user_local_time = utc_now.astimezone(tz)
        user_time_str = user_local_time.strftime("%H:%M")
        user_date = user_local_time.date()
        
        # 1. Check Daily Notification Trigger
        # Trigger if local time matches notification_time and state is IDLE
        if user_time_str == user.notification_time and user.chat_state == "IDLE":
            # Also ensure they haven't already created a daily entry today
            existing_entry = crud.get_daily_entry_by_date(db, user.id, user_date)
            if not existing_entry:
                send_daily_question(user.line_user_id)
                user.chat_state = "AWAITING_DAILY_ENTRY"
                db.commit()
                daily_notifications_sent += 1
                
        # 2. Check Weekly Report Trigger
        # Trigger if day of week matches and time matches
        user_day_of_week = user_local_time.weekday()  # 0 = Monday, ..., 6 = Sunday
        if user_day_of_week == user.report_day_of_week and user_time_str == user.report_time:
            # Report range: last 7 days (ending yesterday)
            end_date = user_date - datetime.timedelta(days=1)
            start_date = end_date - datetime.timedelta(days=6)
            
            # Prevent duplicate generation in the same minute
            existing_report = db.query(models.WeeklyReport).filter(
                and_(
                    models.WeeklyReport.user_id == user.id,
                    models.WeeklyReport.start_date == start_date,
                    models.WeeklyReport.end_date == end_date
                )
            ).first()
            
            if not existing_report:
                # Fetch daily entries for the week
                entries = crud.get_recent_entries_with_answers(db, user.id, start_date, end_date)
                
                # Format entries into Gemini input
                entries_data = []
                for entry in entries:
                    q_answers = {ans.question_key: ans.answer for ans in entry.extra_answers}
                    mapped_answers = {}
                    for k, v in q_answers.items():
                        q_label = QUESTIONS.get(k, k)
                        mapped_answers[q_label] = v
                        
                    entries_data.append({
                        "date": entry.date.strftime("%Y-%m-%d"),
                        "content": entry.content,
                        "extra_answers": mapped_answers
                    })
                
                # Generate report with Gemini
                report_text = generate_weekly_report(user.nickname, entries_data)
                
                # Save report in DB
                crud.create_weekly_report(db, user.id, start_date, end_date, report_text)
                
                # Send weekly report to user via LINE
                push_text(user.line_user_id, f"【ajisai 今週のレポート】\n\n{report_text}")
                weekly_reports_sent += 1
                
    return {
        "status": "success",
        "daily_notifications_sent": daily_notifications_sent,
        "weekly_reports_sent": weekly_reports_sent
    }
