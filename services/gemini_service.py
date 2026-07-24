from google import genai
from config import settings
from typing import List, Dict, Any

def get_gemini_client() -> genai.Client:
    return genai.Client(api_key=settings.GEMINI_API_KEY)

def generate_weekly_report(nickname: str, entries_data: List[Dict[str, Any]]) -> str:
    """
    Generate a warm, counselor-like weekly report using Gemini API.
    
    entries_data format:
    [
        {
            "date": "2026-07-20",
            "content": "Raw diary text",
            "extra_answers": {
                "food": "...",
                "effort": "..."
            }
        },
        ...
    ]
    """
    if not entries_data:
        return "過去1週間の日記データが登録されていないため、今週のレポートを作成できませんでした。来週はぜひ記録をつけてみてくださいね！"

    # Constructing the diary log for the prompt
    diary_log = ""
    for entry in entries_data:
        diary_log += f"■ 日付: {entry['date']}\n"
        diary_log += f"  日記: {entry['content']}\n"
        for q_name, answer in entry.get("extra_answers", {}).items():
            diary_log += f"  - {q_name}: {answer}\n"
        diary_log += "\n"

    prompt = f"""
あなたはユーザーに温かく寄り添う心理カウンセラーでありライフコーチです。
ユーザー（お名前: {nickname or 'あなた'} さん）がこの1週間に記録した日記と定型質問の回答を元に、
今週を振り返り、優しく寄り添うパーソナライズされた週次レポートを生成してください。

【ユーザーの1週間の記録】
{diary_log}

【レポート生成のガイドライン】
1. 1週間の感情の傾向や、ユーザーがどのように過ごしたかを優しく分析してください。
2. ユーザーが「頑張ったこと」や「できたこと」を見つけ、しっかりと褒めて労ってください。
3. 「できなかったこと」や「課題」に対して、前向きになれるような優しいアドバイスやヒントを提示してください。
4. 来週（明日から）に向けて、背中をそっと押すような前向きな言葉（エール）で締めくくってください。
5. LINEのトーク画面で読みやすいよう、適度な改行や記号・絵文字を使用し、親しみやすい丁寧語（です・ます調）で記述してください。
6. 長さは全体で300文字から500文字程度に収めてください。
"""

    try:
        client = get_gemini_client()
        # Use gemini-2.5-flash as default fast model
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        # Fallback to general message if API call fails
        print(f"Error calling Gemini API: {e}")
        return (
            f"今週のレポートをAIで作成中にエラーが発生しました。\n"
            f"ですが、{nickname or 'あなた'}さんが今週一歩一歩進んできたことは間違いありません。今週もお疲れ様でした！"
        )
