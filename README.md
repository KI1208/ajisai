# LINE日記・気分記録アプリ「ajisai」

「ajisai」は、ユーザーが1日1回LINEを通じて手軽に日記や気分を記録し、1週間分の記録をGemini API（AI）が優しく寄り添うトーンで分析した週次レポートとして届ける、LINE botアプリケーションです。

将来の商用化および複数ユーザー利用を視野に入れた、堅牢でスケーラブルなアーキテクチャで設計されています。

---

## 主な機能と特徴

1. **シンプルな日記記録**:
   - 毎日設定した時刻にLINEで日記の問いかけが送信されます。
   - 返信した文章は、そのまま生テキストとしてデータベースに保存されます（AIによる自動分割などは行いません）。
2. **オプションの定型質問（クイックリプライ）**:
   - 日記の回答後、追加で答えたい定型質問（今日食べたもの、頑張ったことなど）をボタンで提示し、インタラクティブに回答を選択できます。回答済みの質問は自動的にリストから除外されます。
3. **AI週次レポート機能**:
   - Gemini API (`gemini-2.5-flash`) を用い、1週間分の日記と質問回答を心理カウンセラーやコーチのような温かい視点で分析・要約したレポートを作成し、自動でLINEにプッシュ送信します。
4. **個人別の時間・曜日設定**:
   - ユーザーごとに、毎日の「通知時刻」や「週次レポートの送信曜日・時刻」を個別に設定可能です。
   - LINEトーク内で「設定」と送信することで、いつでもチャットを通じて設定変更が行えます。

---

## システムアーキテクチャ・技術スタック

* **バックエンド**: FastAPI (Python 3.11+)
* **データベース**: Cloud SQL (PostgreSQL) / 開発・ローカルテスト用には SQLite をサポート
* **インフラ**: Google Cloud Run (Dockerfile 同梱)
* **AIエンジン**: Gemini API (Official `google-genai` SDK)
* **インターフェース**: LINE Messaging API

---

## ディレクトリ構造

```
ajisai/
│
├── main.py                # FastAPIアプリケーション初期化・エントリーポイント
├── config.py              # 環境変数読み込み・管理 (Pydantic settings)
├── database.py            # SQLAlchemy接続・セッション管理
├── models.py              # DBテーブル定義 (User, DailyEntry, ExtraAnswer, WeeklyReport)
├── schemas.py             # Pydanticバリデーションスキーマ
├── crud.py                # データベース操作関数 (CRUD)
│
├── api/
│   ├── webhook.py         # LINE Webhookハンドラー (状態遷移ステートマシン)
│   └── scheduler.py       # Cloud Scheduler用時間監視・ポーリングトリガー
│
├── services/
│   ├── line_service.py    # LINE Messaging APIラッパー
│   └── gemini_service.py  # Gemini APIプロンプト処理
│
├── tests/                 # 単体・結合テストスイート
│   ├── conftest.py        # テスト用DB・モック設定
│   ├── test_webhook.py    # Webhook・ステートマシン遷移テスト
│   └── test_scheduler.py  # スケジューラー起動・時間判定テスト
│
├── Dockerfile             # Cloud Runデプロイ用設定
├── requirements.txt       # 依存ライブラリ一覧
└── README.md              # 本書
```

---

## 開発環境のセットアップと起動方法

### 1. 仮想環境の作成とライブラリのインストール

```powershell
# 仮想環境の作成
python -m venv .venv

# 仮想環境の有効化 (Windows PowerShellの場合)
.\.venv\Scripts\Activate.ps1

# 依存関係のインストール
pip install -r requirements.txt
```

### 2. 環境変数の設定 (`.env` ファイルの作成)
プロジェクトのルートディレクトリに `.env` ファイルを作成し、以下のパラメータを設定します。

```env
LINE_CHANNEL_ACCESS_TOKEN="【LINE Developersで発行したチャネルアクセストークン】"
LINE_CHANNEL_SECRET="【LINE Developersのチャネルシークレット】"
GEMINI_API_KEY="【Google AI Studioで取得したGemini APIキー】"

# 開発用ローカルDB（SQLite）を使用する場合は設定不要
# DATABASE_URL="postgresql://user:password@host/dbname"
```

### 3. アプリケーションの起動
ローカル開発サーバー（Uvicorn）を起動します。初回起動時に自動でローカルの SQLite データベース (`ajisai.db`) が生成されます。

```powershell
.\.venv\Scripts\uvicorn main:app --reload
```
サーバーは `http://127.0.0.1:8000` で立ち上がります。

---

## LINE Developers での設定手順

1. **プロバイダーとチャネルの作成**:
   - [LINE Developers Console](https://developers.line.biz/) にログインし、「Messaging API」チャネルを新規作成します。
2. **キーの設定**:
   - 「基本設定」タブの **チャネルシークレット** を `.env` の `LINE_CHANNEL_SECRET` にコピーします。
   - 「Messaging API設定」タブ最下部の **チャネルアクセストークン（長期）** を発行し、`.env` の `LINE_CHANNEL_ACCESS_TOKEN` にコピーします。
3. **Webhook URL の登録**:
   - `ngrok` 等でローカルサーバーを外部公開します：
     ```bash
     ngrok http 8000
     ```
   - 発行された `https://xxxx.ngrok-free.app` 形式のドメインを使って、LINE Developersの「Webhook URL」に以下を登録します。
     * **Webhook URL**: `https://xxxx.ngrok-free.app/api/webhook` （※末尾の `/api/webhook` が必須です）
   - **「Webhookの利用」** スイッチを **ON** にします。
4. **自動応答のオフ設定 (重複返信防止)**:
   - 「Messaging API設定」タブの「応答メッセージ」の編集リンクをクリックし、LINE Official Account Managerの応答設定で、**「応答メッセージ」をオフ**、**「Webhook」をオン**にします。
5. **友だち追加**:
   - 「Messaging API設定」タブのQRコードからLINEアカウントを友だち追加します。

---

## トーク画面での使い方

* **日記の記録**:
  設定した時間になるとボットから問いかけが来ます。メッセージを返信すると、そのまま今日の日記として記録されます。
* **追加の質問に答える**:
  日記回答後、クイックリプライで「今日何を食べた？」「今日頑張ったことは？」などのボタンが表示されます。タップして回答を入力できます。「回答を終了する」で終了します。
* **個人設定の変更**:
  チャットで **`設定`** と送信すると、設定メニューボタンが表示されます。
  - 「通知時間の変更」: 例として `22:15` のように24時間表記で送信して変更します。
  - 「レポート設定の変更」: 例として `月曜 08:30` のように曜日と時間をスペース区切りで送信して変更します。
* **対話のキャンセル**:
  途中で入力を止めたい場合は、`キャンセル` または `終了` と送信すると `IDLE` 状態に戻ります。

---

## 定期実行タスクの検証方法 (開発用)

本番環境では GCP Cloud Scheduler 等から毎分/毎時間 `/api/scheduler/check-triggers` が叩かれ、設定時間になったユーザーへ処理を実行します。
開発中に動作を確認したい場合は、以下のエンドポイントを手動で叩く（POST）ことで、その時点で通知または週次レポートの基準を満たしたユーザーに対する送信が即座に実行されます。

```bash
curl -X POST "http://127.0.0.1:8000/api/scheduler/check-triggers?api_key=change_me_in_production"
```
※ `api_key` は `.env` または `config.py` 内の `SCHEDULER_API_KEY` と一致している必要があります。

---

## テストの実行方法

自動テストを起動して、ステートマシンやスケジューラーのトリガー時間判定ロジックが正常に動作するか検証します。テスト実行時は自動的にメモリ上の SQLite が使用され、モックにより実際の外部通信は発生しません。

```powershell
.\.venv\Scripts\pytest
```
