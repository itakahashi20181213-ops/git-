# LINE株価通知システム（クラウド実行 / Git運用）

登録した銘柄の株価を定期送信できるように、以下の構成で作成しています。

- `src/message_builder.py`: 通知本文を組み立てる
- `src/stock_client.py`: 株価情報の取得（Yahoo Finance）
- `src/line_client.py`: LINE Messaging APIへ送信
- `src/main.py`: 実行エントリーポイント
- `src/webhook_server.py`: LINEからの銘柄追加/削除コマンド受付
- `config/stocks.txt`: 登録銘柄リスト（1行1銘柄）
- `config/settings.json`: しきい値設定（%）
- `.github/workflows/line-notify.yml`: GitHub Actions でのクラウド実行設定

## 事前準備（LINE側）

1. LINE Developersで Messaging API のチャネルを作成
2. `Channel access token` を発行
3. 送信先の `userId` / `groupId` / `roomId` を取得（`LINE_TO` として使用）

## GitHub Secrets

このリポジトリの Secrets に以下を登録してください。

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_TO`
- `LINE_CHANNEL_SECRET`（Webhook用）
- （任意）`STOCK_SYMBOLS`（カンマ区切り。例: `7203.T,6758.T,AAPL`）
- （Webhookサーバー用）`GITHUB_TOKEN_FOR_CONFIG`（repo 権限）
- （Webhookサーバー用）`GITHUB_REPOSITORY`（例: `itakahashi20181213-ops/git-`）
- （Webhookサーバー用・任意）`GITHUB_BRANCH`（既定: `main`）

## 実行方法

### クラウド実行（推奨）

- GitHub Actions の `LINE Notify` ワークフローを手動実行（`workflow_dispatch`）
- または毎時実行（cron設定済み）
- `config/settings.json` の `change_threshold_percent` 以上の変動がある銘柄だけ送信

### ローカル確認

```powershell
pip install -r requirements.txt
$env:LINE_CHANNEL_ACCESS_TOKEN="YOUR_TOKEN"
$env:LINE_TO="YOUR_USER_OR_GROUP_ID"
# 任意: ファイルより優先して銘柄を指定
# $env:STOCK_SYMBOLS="7203.T,6758.T,AAPL"
python src/main.py
```

## 銘柄の登録方法

### 方法1（推奨）

`config/stocks.txt` に1行ずつ銘柄コードを記載します。

```txt
7203.T
6758.T
AAPL
```

### 方法2（Secrets）

GitHub Secrets の `STOCK_SYMBOLS` を使うと、`config/stocks.txt` より優先されます。

## しきい値設定

- 既定値は `config/settings.json` の `2.0`（= ±2.0%以上）
- しきい値未満しかない場合は、通知を送信しません

## LINEから銘柄を追加/削除する

`src/webhook_server.py` をクラウドにデプロイし、LINE Developers の Webhook URL を
`https://<your-domain>/callback` に設定します。

起動例:

```powershell
uvicorn src.webhook_server:app --host 0.0.0.0 --port 8000
```

LINEで送れるコマンド:

```txt
追加 7203.T
削除 7203.T
一覧
しきい値 2.0
ヘルプ
```

Webhookで変更された `config/stocks.txt` / `config/settings.json` は GitHub API 経由で
リポジトリへ反映され、次回の定期通知から自動適用されます。

## Render でデプロイする（Webhook用）

このリポジトリには `render.yaml` を用意してあるので、Blueprint デプロイができます。

1. Render に GitHub 連携してこのリポジトリを選択
2. Blueprint として作成（`render.yaml` が自動読込されます）
3. 以下の環境変数を設定
   - `LINE_CHANNEL_ACCESS_TOKEN`
   - `LINE_CHANNEL_SECRET`
   - `GITHUB_TOKEN_FOR_CONFIG`
   - `GITHUB_REPOSITORY`（例: `itakahashi20181213-ops/git-`）
   - `GITHUB_BRANCH`（任意、既定は `main`）
4. デプロイ完了後、公開URLの `/callback` を LINE Developers の Webhook URL に設定
   - 例: `https://line-stock-webhook.onrender.com/callback`
5. LINE Developers で Webhook を有効化して、接続確認を実施
