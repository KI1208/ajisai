# LINE日記・週次レポートアプリ「ajisai」デプロイガイド

本ドキュメントでは、**Google Cloud Run**、**Supabase (PostgreSQL)**、**Google Secret Manager** を活用した「ajisai」の完全デプロイ手順を解説します。

---

## 🏗️ 全体アーキテクチャ概要

| コンポーネント | 採用技術 | 役割 |
| :--- | :--- | :--- |
| **バックエンド** | FastAPI (Python 3.11) | Web API / LINE Webhook処理 / スケジューラーエンドポイント |
| **ホスティング** | Google Cloud Run | コンテナ型サーバーレス実行環境 (自動スケール / HTTPS対応) |
| **データベース** | Supabase (PostgreSQL) | ユーザー情報・日記・週次レポートデータの永続化 |
| **機密情報管理** | Google Secret Manager | APIキーやDB接続URLの安全な暗号化保管 |
| **定期トリガー** | Google Cloud Scheduler | 毎分の通知判定・週次レポート配信トリガー (1分間隔) |
| **AI処理** | Gemini API (`gemini-2.5-flash`) | 日記要約および週次アドバイスレポートの自動生成 |
| **UI/通知** | LINE Messaging API | ユーザーインターフェース (通知・クイックリプライ・レポート受信) |

---

## 📋 事前準備チェックリスト

1. **Google Cloud CLI (`gcloud`)** がインストールされ、対象プロジェクトにログイン済みであること
2. **Supabase** でプロジェクトを作成し、**PostgreSQL 接続文字列 (Database URL)** を取得済みであること
   * 例: `postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres`
   * ※パスワード内の特殊文字はURLエンコードが必要な場合があります。
3. **LINE Developers** で Messaging API チャネルを作成し、以下を取得済みであること
   * `LINE_CHANNEL_ACCESS_TOKEN` (長期チャネルアクセストークン)
   * `LINE_CHANNEL_SECRET` (チャネルシークレット)
4. **Google AI Studio** で `GEMINI_API_KEY` を取得済みであること

---

## 🔒 Step 1: Secret Manager への機密情報登録

環境変数をソースコードやデプロイコマンドの引数に直書きせず、Secret Manager に登録して安全に管理します。

### 1.1 Secret Manager API の有効化
```bash
gcloud services enable secretmanager.googleapis.com
```

### 1.2 各シークレットの作成と値の保存

以下の5つのシークレットを作成します。

#### ① LINE Channel Access Token
```bash
gcloud secrets create line-access-token --replication-policy="automatic"
echo -n "YOUR_LINE_ACCESS_TOKEN" | gcloud secrets versions add line-access-token --data-file=-
```

#### ② LINE Channel Secret
```bash
gcloud secrets create line-secret --replication-policy="automatic"
echo -n "YOUR_LINE_CHANNEL_SECRET" | gcloud secrets versions add line-secret --data-file=-
```

#### ③ Gemini API Key
```bash
gcloud secrets create gemini-api-key --replication-policy="automatic"
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets versions add gemini-api-key --data-file=-
```

#### ④ Supabase DATABASE_URL
```bash
gcloud secrets create database-url --replication-policy="automatic"
echo -n "postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres" | gcloud secrets versions add database-url --data-file=-
```

#### ⑤ SCHEDULER_API_KEY (合い言葉)
```bash
gcloud secrets create scheduler-api-key --replication-policy="automatic"
echo -n "YOUR_RANDOM_SECRET_KEY" | gcloud secrets versions add scheduler-api-key --data-file=-
```

---

## 🔑 Step 2: Cloud Run サービスアカウントへの権限付与

Cloud Run が Secret Manager から安全にシークレットを読み込めるよう、サービスアカウントに権限を付与します。

```bash
# プロジェクト番号の取得
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format="value(projectNumber)")

# デフォルトの Compute / Cloud Run サービスアカウントに Secret Accessor 権限を付与
gcloud projects add-iam-policy-binding $(gcloud config get-value project) \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

---

## 🚀 Step 3: Cloud Run へのデプロイ

`--set-secrets` オプションを使用して、Secret Manager 内のシークレットを環境変数にマッピングしてデプロイします。

### PowerShell (Windows) の場合:
```powershell
gcloud run deploy ajisai `
  --source . `
  --region asia-northeast1 `
  --allow-unauthenticated `
  --set-secrets="LINE_CHANNEL_ACCESS_TOKEN=line-access-token:latest,LINE_CHANNEL_SECRET=line-secret:latest,GEMINI_API_KEY=gemini-api-key:latest,DATABASE_URL=database-url:latest,SCHEDULER_API_KEY=scheduler-api-key:latest"
```

### Bash / Linux / macOS の場合:
```bash
gcloud run deploy ajisai \
  --source . \
  --region asia-northeast1 \
  --allow-unauthenticated \
  --set-secrets="LINE_CHANNEL_ACCESS_TOKEN=line-access-token:latest,LINE_CHANNEL_SECRET=line-secret:latest,GEMINI_API_KEY=gemini-api-key:latest,DATABASE_URL=database-url:latest,SCHEDULER_API_KEY=scheduler-api-key:latest"
```

デプロイ完了後、ターミナルに表示される **Service URL** をメモします（例: `https://ajisai-xxxxxx-an.a.run.app`）。

---

## 💬 Step 4: LINE Webhook の設定

1. [LINE Developers コンソール](https://developers.line.biz/) にログインします。
2. 対象チャネルの **「Messaging API設定」** タブを開きます。
3. **Webhook URL** に以下を設定します：
   ```
   https://ajisai-xxxxxx-an.a.run.app/api/webhook
   ```
4. **「Webhookの利用」** を **ON** に変更します。
5. **「検証」** ボタンを押し、`200 Success` が表示されることを確認します。
6. 同ページ内の **「応答メッセージ」** を **無効**（応答モード: チャット または Bot、詳細設定で自動応答をオフ）に設定します。

---

## ⏰ Step 5: Cloud Scheduler (定期トリガー) の設定

毎日・毎週の通知および週次レポート生成を自動チェックするため、1分間隔の定期ジョブを作成します。

### PowerShell の場合:
```powershell
gcloud scheduler jobs create http ajisai-trigger-job `
  --schedule="* * * * *" `
  --uri="https://ajisai-xxxxxx-an.a.run.app/api/scheduler/check-triggers" `
  --http-method=POST `
  --headers="X-Scheduler-Key=YOUR_RANDOM_SECRET_KEY" `
  --time-zone="Asia/Tokyo"
```

*(※ `--headers` の `YOUR_RANDOM_SECRET_KEY` には Step 1.2 ⑤ で設定した文字列を指定します)*

---

## 🔍 Step 6: 動作確認とテスト

1. **ヘルスチェック**:
   ブラウザで `https://ajisai-xxxxxx-an.a.run.app/` にアクセスし、`{"message": "ajisai API is running smoothly!"}` が返ることを確認します。
2. **Supabase テーブル自動生成の確認**:
   Cloud Run 起動時 (`main.py` の `lifespan`) に Supabase 上へ `users`, `daily_entries`, `extra_answers`, `weekly_reports` テーブルが自動作成されていることを Supabase Dashboard の **Table Editor** で確認します。
3. **LINE トークテスト**:
   LINE 公式アカウントに友達追加し、メッセージを送信して自動返答・クイックリプライが動作することを確認します。

---

## 🛠️ トラブルシューティング & 運用ログ

* **Cloud Run のリアルタイムログ確認**:
  ```bash
  gcloud run services logs tail ajisai --region=asia-northeast1
  ```
* **Supabase 接続エラーの場合**:
  * 接続文字列 `postgresql://...` のパスワード特殊文字が原因であることがあります。必要に応じてエンコードしてください。
  * Supabase の Connection Pooling (Transaction / Session 5432 または 6543) を利用することも可能です。
