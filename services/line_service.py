from linebot import LineBotApi
from linebot.models import (
    TextSendMessage, QuickReply, QuickReplyButton, PostbackAction, 
    TemplateSendMessage, ButtonsTemplate
)
from config import settings
from typing import List, Dict

line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)

QUESTIONS: Dict[str, str] = {
    "food": "今日何を食べた？",
    "effort": "今日頑張ったことは？",
    "failed": "今日できなかったことは？",
    "tomorrow": "明日やりたいことは？"
}

def reply_text(reply_token: str, text: str, quick_reply: QuickReply = None):
    """Send a text reply to a user."""
    message = TextSendMessage(text=text, quick_reply=quick_reply)
    line_bot_api.reply_message(reply_token, message)

def push_text(to_user_id: str, text: str, quick_reply: QuickReply = None):
    """Push a text message to a user."""
    message = TextSendMessage(text=text, quick_reply=quick_reply)
    line_bot_api.push_message(to_user_id, message)

def send_daily_question(to_user_id: str):
    """Send the initial daily diary prompt."""
    text = "【ajisai日記の問いかけ】\n今日も一日お疲れ様でした！今日の気分や出来事を教えてください。"
    push_text(to_user_id, text)

def send_question_selection(to_user_id: str, reply_token: str, answered_keys: List[str]):
    """Send quick replies of remaining optional questions."""
    buttons = []
    
    for key, val in QUESTIONS.items():
        if key not in answered_keys:
            buttons.append(
                QuickReplyButton(
                    action=PostbackAction(
                        label=val,
                        data=f"action=select_q&key={key}",
                        displayText=f"「{val}」に回答する"
                    )
                )
            )
            
    # Add a finish button
    buttons.append(
        QuickReplyButton(
            action=PostbackAction(
                label="回答を終了する",
                data="action=finish_entry",
                displayText="回答を終了する"
            )
        )
    )
    
    quick_reply = QuickReply(items=buttons)
    text = "日記を記録しました！追加で以下の質問にも答えますか？回答したい質問を選択してください。"
    
    if reply_token:
        reply_text(reply_token, text, quick_reply=quick_reply)
    else:
        push_text(to_user_id, text, quick_reply=quick_reply)

def send_settings_menu(to_user_id: str, reply_token: str):
    """Send settings menu template."""
    template = ButtonsTemplate(
        title="各種設定",
        text="変更したい項目を選択してください。",
        actions=[
            PostbackAction(
                label="通知時間の変更",
                data="action=settings_select&param=notify",
                displayText="通知時間を変更する"
            ),
            PostbackAction(
                label="レポート設定の変更",
                data="action=settings_select&param=report",
                displayText="レポート設定を変更する"
            )
        ]
    )
    
    message = TemplateSendMessage(
        alt_text="設定メニュー",
        template=template
    )
    
    if reply_token:
        line_bot_api.reply_message(reply_token, message)
    else:
        line_bot_api.push_message(to_user_id, message)
