import pytest
from unittest.mock import patch, MagicMock
import datetime
from zoneinfo import ZoneInfo
import models
import crud
from config import settings

def test_scheduler_unauthorized(client):
    response = client.post("/api/scheduler/check-triggers")
    assert response.status_code == 401
    
    response = client.post("/api/scheduler/check-triggers?api_key=wrong_key")
    assert response.status_code == 401

def test_scheduler_daily_notification_trigger(client, db_session, mock_external_services, monkeypatch):
    # Setup active user with notification_time = "21:00"
    user_id = "U44444444444444444444444444444444"
    db_user = models.User(
        line_user_id=user_id,
        nickname= "Dave",
        notification_time="21:00",
        timezone="Asia/Tokyo",
        chat_state="IDLE",
        is_active=True
    )
    db_session.add(db_user)
    db_session.commit()

    # We want user's local time in Asia/Tokyo to be 21:00.
    # 21:00 JST is 12:00 UTC.
    mock_utc_now = datetime.datetime(2026, 7, 24, 12, 0, 0, tzinfo=datetime.timezone.utc)
    
    # Patch get_now_utc in api.scheduler
    monkeypatch.setattr("api.scheduler.get_now_utc", lambda: mock_utc_now)

    # Call scheduler trigger
    response = client.post(
        f"/api/scheduler/check-triggers?api_key={settings.SCHEDULER_API_KEY}"
    )
    assert response.status_code == 200
    assert response.json()["daily_notifications_sent"] == 1
    
    # Check user state changed to AWAITING_DAILY_ENTRY
    db_session.refresh(db_user)
    assert db_user.chat_state == "AWAITING_DAILY_ENTRY"
    
    # Check that LINE service sent daily question
    mock_external_services["send_daily_question"].assert_called_once_with(user_id)

def test_scheduler_weekly_report_trigger(client, db_session, mock_external_services, monkeypatch):
    # Setup active user with report_day_of_week = 0 (Monday), report_time = "09:00"
    user_id = "U55555555555555555555555555555555"
    db_user = models.User(
        line_user_id=user_id,
        nickname="Eve",
        report_day_of_week=0,  # Monday
        report_time="09:00",
        timezone="Asia/Tokyo",
        chat_state="IDLE",
        is_active=True
    )
    db_session.add(db_user)
    db_session.commit()

    # Add a few daily entries for this user
    local_date = datetime.date(2026, 7, 20)  # Monday
    entry = models.DailyEntry(user_id=db_user.id, date=local_date, content="月曜日の日記")
    db_session.add(entry)
    
    local_date2 = datetime.date(2026, 7, 21) # Tuesday
    entry2 = models.DailyEntry(user_id=db_user.id, date=local_date2, content="火曜日の日記")
    db_session.add(entry2)
    db_session.commit()

    # We want local time to be Monday, July 27, 2026 at 09:00 JST.
    # 09:00 JST is 00:00 UTC.
    # July 27, 2026 is indeed a Monday.
    mock_utc_now = datetime.datetime(2026, 7, 27, 0, 0, 0, tzinfo=datetime.timezone.utc)
    
    # Patch get_now_utc in api.scheduler
    monkeypatch.setattr("api.scheduler.get_now_utc", lambda: mock_utc_now)

    # Call scheduler
    response = client.post(
        f"/api/scheduler/check-triggers?api_key={settings.SCHEDULER_API_KEY}"
    )
    assert response.status_code == 200
    assert response.json()["weekly_reports_sent"] == 1

    # Check report was saved in DB
    report = db_session.query(models.WeeklyReport).filter(models.WeeklyReport.user_id == db_user.id).first()
    assert report is not None
    assert report.report_content == "Mocked AI report for the week."
    # Date range should be last week: Monday, July 20 to Sunday, July 26
    assert report.start_date == datetime.date(2026, 7, 20)
    assert report.end_date == datetime.date(2026, 7, 26)

    # Check weekly report was sent to LINE
    mock_external_services["push_text"].assert_called_once_with(
        user_id,
        "【ajisai 今週のレポート】\n\nMocked AI report for the week."
    )
