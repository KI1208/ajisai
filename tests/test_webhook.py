import pytest
from unittest.mock import patch, MagicMock
from linebot.models import MessageEvent, TextMessage, PostbackEvent, SourceUser
import models
import crud
from api.webhook import get_user_local_date

def create_mock_text_event(user_id: str, text: str) -> MessageEvent:
    event = MagicMock(spec=MessageEvent)
    event.type = "message"
    event.source = MagicMock(spec=SourceUser)
    event.source.user_id = user_id
    event.message = MagicMock(spec=TextMessage)
    event.message.type = "text"
    event.message.text = text
    event.reply_token = "dummy_reply_token"
    return event

def create_mock_postback_event(user_id: str, data: str) -> PostbackEvent:
    event = MagicMock(spec=PostbackEvent)
    event.type = "postback"
    event.source = MagicMock(spec=SourceUser)
    event.source.user_id = user_id
    event.postback = MagicMock()
    event.postback.data = data
    event.reply_token = "dummy_reply_token"
    return event

def test_webhook_register_and_create_diary(client, db_session, mock_external_services):
    user_id = "U11111111111111111111111111111111"
    
    # 1. Simulate user sending text message "IDLE" state -> creates diary entry
    mock_event = create_mock_text_event(user_id, "今日はすごくいい一日だった。美味しいランチを食べた。")
    
    with patch("api.webhook.parser.parse", return_value=[mock_event]):
        response = client.post(
            "/api/webhook",
            headers={"X-Line-Signature": "dummy_signature"}
        )
        assert response.status_code == 200
        
        # Verify user was created
        user = crud.get_user_by_line_id(db_session, user_id)
        assert user is not None
        assert user.nickname == "Test User"
        assert user.chat_state == "AWAITING_QUESTION_SELECTION"
        
        # Verify daily entry was created
        entry = crud.get_daily_entry_by_date(db_session, user.id, get_user_local_date(user.timezone))
        assert entry is not None
        assert entry.content == "今日はすごくいい一日だった。美味しいランチを食べた。"
        
        # Verify selection menu was sent
        mock_external_services["send_question_selection"].assert_called_once_with(user_id, "dummy_reply_token", [])

def test_webhook_state_machine_flow(client, db_session, mock_external_services):
    user_id = "U22222222222222222222222222222222"
    
    # Setup user in AWAITING_QUESTION_SELECTION state
    db_user = models.User(line_user_id=user_id, nickname="Alice", chat_state="AWAITING_QUESTION_SELECTION")
    db_session.add(db_user)
    db_session.commit()
    
    # Also create the entry for today (required to attach answers)
    local_date = get_user_local_date(db_user.timezone)
    entry = models.DailyEntry(user_id=db_user.id, date=local_date, content="日記本文")
    db_session.add(entry)
    db_session.commit()

    # 1. Postback: Select "food" question
    postback_event = create_mock_postback_event(user_id, "action=select_q&key=food")
    with patch("api.webhook.parser.parse", return_value=[postback_event]):
        response = client.post("/api/webhook", headers={"X-Line-Signature": "dummy"})
        assert response.status_code == 200
        
        # Check user state changed to AWAITING_ANSWER:food
        db_session.refresh(db_user)
        assert db_user.chat_state == "AWAITING_ANSWER:food"
        mock_external_services["reply_text"].assert_any_call("dummy_reply_token", "「今日何を食べた？」の回答を入力してください。")

    # 2. Text message: Reply to "food" question
    reply_event = create_mock_text_event(user_id, "ラーメンと餃子")
    with patch("api.webhook.parser.parse", return_value=[reply_event]):
        response = client.post("/api/webhook", headers={"X-Line-Signature": "dummy"})
        assert response.status_code == 200
        
        # Check state transitioned back to selection
        db_session.refresh(db_user)
        assert db_user.chat_state == "AWAITING_QUESTION_SELECTION"
        
        # Verify answer was saved
        db_session.refresh(entry)
        assert len(entry.extra_answers) == 1
        assert entry.extra_answers[0].question_key == "food"
        assert entry.extra_answers[0].answer == "ラーメンと餃子"
        
        # Verify selection menu was re-sent with "food" in answered list
        mock_external_services["send_question_selection"].assert_any_call(user_id, "dummy_reply_token", ["food"])

def test_webhook_settings_flow(client, db_session, mock_external_services):
    user_id = "U33333333333333333333333333333333"
    db_user = models.User(line_user_id=user_id, nickname="Bob", chat_state="IDLE")
    db_session.add(db_user)
    db_session.commit()
    
    # 1. Text message: "設定" -> Open settings menu
    event_settings = create_mock_text_event(user_id, "設定")
    with patch("api.webhook.parser.parse", return_value=[event_settings]):
        client.post("/api/webhook", headers={"X-Line-Signature": "dummy"})
        mock_external_services["send_settings_menu"].assert_called_once_with(user_id, "dummy_reply_token")
        
    # 2. Postback: Change notification time
    postback_notify = create_mock_postback_event(user_id, "action=settings_select&param=notify")
    with patch("api.webhook.parser.parse", return_value=[postback_notify]):
        client.post("/api/webhook", headers={"X-Line-Signature": "dummy"})
        db_session.refresh(db_user)
        assert db_user.chat_state == "AWAITING_SETTING:notification_time"
        
    # 3. Text message: Send invalid time "99:99"
    event_invalid_time = create_mock_text_event(user_id, "99:99")
    with patch("api.webhook.parser.parse", return_value=[event_invalid_time]):
        client.post("/api/webhook", headers={"X-Line-Signature": "dummy"})
        db_session.refresh(db_user)
        assert db_user.chat_state == "AWAITING_SETTING:notification_time" # should stay
        mock_external_services["reply_text"].assert_any_call("dummy_reply_token", "時間のフォーマットが正しくありません。24時間表記の「HH:MM」（例: 21:00）で入力してください。")
        
    # 4. Text message: Send valid time "22:15"
    event_valid_time = create_mock_text_event(user_id, "22:15")
    with patch("api.webhook.parser.parse", return_value=[event_valid_time]):
        client.post("/api/webhook", headers={"X-Line-Signature": "dummy"})
        db_session.refresh(db_user)
        assert db_user.chat_state == "IDLE"
        assert db_user.notification_time == "22:15"
