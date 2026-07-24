from fastapi import APIRouter, Request, Header, HTTPException, Depends
from sqlalchemy.orm import Session
from urllib.parse import parse_qs
import re
import datetime
from zoneinfo import ZoneInfo

from linebot.v3.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, PostbackEvent
from linebot import WebhookParser

from config import settings
from database import get_db
import crud
import schemas
from services.line_service import (
    line_bot_api, reply_text, send_question_selection, send_settings_menu, QUESTIONS
)

router = APIRouter(prefix="/api", tags=["webhook"])
parser = WebhookParser(settings.LINE_CHANNEL_SECRET)

# Helper to map day names to integer (0: Monday, ..., 6: Sunday)
DAY_MAP = {
    "月": 0, "月曜": 0, "月曜日": 0, "mon": 0, "monday": 0,
    "火": 1, "火曜": 1, "火曜日": 1, "tue": 1, "tuesday": 1,
    "水": 2, "水曜": 2, "水曜日": 2, "wed": 2, "wednesday": 2,
    "木": 3, "木曜": 3, "木曜日": 3, "thu": 3, "thursday": 3,
    "金": 4, "金曜": 4, "金曜日": 4, "fri": 4, "friday": 4,
    "土": 5, "土曜": 5, "土曜日": 5, "sat": 5, "saturday": 5,
    "日": 6, "日曜": 6, "日曜日": 6, "sun": 6, "sunday": 6,
}
REV_DAY_MAP = {0: "月曜日", 1: "火曜日", 2: "水曜日", 3: "木曜日", 4: "金曜日", 5: "土曜日", 6: "日曜日"}

def get_user_local_date(timezone_str: str) -> datetime.date:
    """Get the current local date for a given timezone string."""
    try:
        tz = ZoneInfo(timezone_str)
        return datetime.datetime.now(tz).date()
    except Exception:
        # Fallback to JST (UTC+9)
        utc_now = datetime.datetime.utcnow()
        jst_now = utc_now + datetime.timedelta(hours=9)
        return jst_now.date()

@router.post("/webhook")
async def line_webhook(
    request: Request,
    x_line_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    if not x_line_signature:
        raise HTTPException(status_code=400, detail="Missing Signature")
    
    body = await request.body()
    body_str = body.decode("utf-8")
    
    try:
        events = parser.parse(body_str, x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid Signature")
    
    for event in events:
        line_user_id = event.source.user_id
        
        # 1. Get or create user
        user = crud.get_user_by_line_id(db, line_user_id)
        if not user:
            # Try to fetch nickname from LINE profile
            try:
                profile = line_bot_api.get_profile(line_user_id)
                nickname = profile.display_name
            except Exception:
                nickname = "ユーザー"
                
            user_create = schemas.UserCreate(
                line_user_id=line_user_id,
                nickname=nickname
            )
            user = crud.create_user(db, user_create)
            
        # 2. Handle Text Messages
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
            user_text = event.message.text.strip()
            
            # Global commands (Settings, Cancel, Help)
            if user_text == "設定":
                crud.update_user(db, user.id, schemas.UserUpdate(chat_state="IDLE"))
                send_settings_menu(user.line_user_id, event.reply_token)
                continue
                
            if user_text in ["キャンセル", "終了", "戻る"]:
                crud.update_user(db, user.id, schemas.UserUpdate(chat_state="IDLE"))
                reply_text(event.reply_token, "対話を終了しました。")
                continue
            
            # Handle states
            state = user.chat_state
            
            if state == "IDLE":
                # If user randomly types text, treat it as a new daily entry.
                local_date = get_user_local_date(user.timezone)
                crud.create_or_update_daily_entry(db, user.id, local_date, user_text)
                crud.update_user(db, user.id, schemas.UserUpdate(chat_state="AWAITING_QUESTION_SELECTION"))
                
                # Fetch answered questions for today to filter selection
                entry = crud.get_daily_entry_by_date(db, user.id, local_date)
                answered = [ans.question_key for ans in entry.extra_answers] if entry else []
                send_question_selection(user.line_user_id, event.reply_token, answered)
                
            elif state == "AWAITING_DAILY_ENTRY":
                # Save daily entry
                local_date = get_user_local_date(user.timezone)
                crud.create_or_update_daily_entry(db, user.id, local_date, user_text)
                crud.update_user(db, user.id, schemas.UserUpdate(chat_state="AWAITING_QUESTION_SELECTION"))
                
                send_question_selection(user.line_user_id, event.reply_token, [])
                
            elif state == "AWAITING_QUESTION_SELECTION":
                # If they type manually instead of clicking quick replies, guide them
                local_date = get_user_local_date(user.timezone)
                entry = crud.get_daily_entry_by_date(db, user.id, local_date)
                answered = [ans.question_key for ans in entry.extra_answers] if entry else []
                reply_text(
                    event.reply_token,
                    "選択肢ボタンから回答したい質問を選んでタップしてください。「回答を終了する」を選ぶと記録を終了します。"
                )
                
            elif state.startswith("AWAITING_ANSWER:"):
                # Extract key
                q_key = state.split(":")[1]
                local_date = get_user_local_date(user.timezone)
                
                # Ensure entry exists
                entry = crud.get_daily_entry_by_date(db, user.id, local_date)
                if not entry:
                    # Edge case: entry expired or not found, create dummy entry
                    entry = crud.create_or_update_daily_entry(db, user.id, local_date, "（日記本文なし）")
                
                # Save answer
                crud.create_or_update_extra_answer(db, entry.id, q_key, user_text)
                
                # Return to selection state
                crud.update_user(db, user.id, schemas.UserUpdate(chat_state="AWAITING_QUESTION_SELECTION"))
                
                # Refresh entry and answered keys
                entry = crud.get_daily_entry_by_date(db, user.id, local_date)
                answered = [ans.question_key for ans in entry.extra_answers] if entry else []
                
                # Check if all questions answered
                if len(answered) >= len(QUESTIONS):
                    crud.update_user(db, user.id, schemas.UserUpdate(chat_state="IDLE"))
                    reply_text(event.reply_token, "すべての質問に回答いただきありがとうございました！今日も一日お疲れ様でした。")
                else:
                    send_question_selection(user.line_user_id, event.reply_token, answered)
                    
            elif state == "AWAITING_SETTING:notification_time":
                # Validate HH:MM
                if re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", user_text):
                    crud.update_user(db, user.id, schemas.UserUpdate(
                        notification_time=user_text,
                        chat_state="IDLE"
                    ))
                    reply_text(event.reply_token, f"毎日の通知時間を {user_text} に設定しました。")
                else:
                    reply_text(event.reply_token, "時間のフォーマットが正しくありません。24時間表記の「HH:MM」（例: 21:00）で入力してください。")
                    
            elif state == "AWAITING_SETTING:report_time":
                # Expected format: "月曜 09:00"
                parts = user_text.split()
                if len(parts) == 2:
                    day_part, time_part = parts[0], parts[1]
                    # Map day
                    day_idx = DAY_MAP.get(day_part.lower())
                    is_time_valid = re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", time_part)
                    
                    if day_idx is not None and is_time_valid:
                        crud.update_user(db, user.id, schemas.UserUpdate(
                            report_day_of_week=day_idx,
                            report_time=time_part,
                            chat_state="IDLE"
                        ))
                        day_name = REV_DAY_MAP[day_idx]
                        reply_text(event.reply_token, f"週次レポートの送信日時を 毎週{day_name}の {time_part} に設定しました。")
                    else:
                        reply_text(event.reply_token, "形式が正しくないか、曜日/時刻の指定が誤っています。\n例: 「月曜 08:30」のように入力してください。")
                else:
                    reply_text(event.reply_token, "曜日と時刻をスペースで区切って入力してください。\n例: 「月曜 08:30」")

        # 3. Handle Postback Events
        elif isinstance(event, PostbackEvent):
            data_str = event.postback.data
            params = parse_qs(data_str)
            
            action = params.get("action", [None])[0]
            
            if action == "select_q":
                key = params.get("key", [None])[0]
                q_text = QUESTIONS.get(key)
                if q_text:
                    crud.update_user(db, user.id, schemas.UserUpdate(chat_state=f"AWAITING_ANSWER:{key}"))
                    reply_text(event.reply_token, f"「{q_text}」の回答を入力してください。")
                    
            elif action == "finish_entry":
                crud.update_user(db, user.id, schemas.UserUpdate(chat_state="IDLE"))
                reply_text(event.reply_token, "日記の記録を終了しました！今日も一日お疲れ様でした。")
                
            elif action == "settings_select":
                param = params.get("param", [None])[0]
                if param == "notify":
                    crud.update_user(db, user.id, schemas.UserUpdate(chat_state="AWAITING_SETTING:notification_time"))
                    reply_text(event.reply_token, "毎日の日記の問いかけを送信する時間を、24時間表記の「HH:MM」（例: 21:30）で入力してください。")
                elif param == "report":
                    crud.update_user(db, user.id, schemas.UserUpdate(chat_state="AWAITING_SETTING:report_time"))
                    reply_text(
                        event.reply_token,
                        "週次レポートを送信する曜日と時間を、「曜日 時刻」（例: 月曜 08:30）の形式で入力してください。\n※曜日は 月/火/水/木/金/土/日 から選択できます。"
                    )
                    
    return {"status": "ok"}
