# LINE株価通知システム（クラウド実行 / Git運用）

登録した銘柄の株価を定期送信できるように、以下の構成で作成しています。

- `src/message_builder.py`: 通知本文を組み立てる
- `src/stock_client.py`: 株価情報の取得（Yahoo Finance）
- `src/line_client.py`: LINE Messaging APIへ送信
- `src/main.py`: 実行エントリーポイント
- `config/stocks.txt`: 登録銘柄リスト（1行1銘柄）
- `.github/workflows/line-notify.yml`: GitHub Actions でのクラウド実行設定

## 事前準備（LINE側）

1. LINE Developersで Messaging API のチャネルを作成
2. `Channel access token` を発行
3. 送信先の `userId` / `groupId` / `roomId` を取得（`LINE_TO` として使用）

## GitHub Secrets

このリポジトリの Secrets に以下を登録してください。

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_TO`
- （任意）`STOCK_SYMBOLS`（カンマ区切り。例: `7203.T,6758.T,AAPL`）

## 実行方法

### クラウド実行（推奨）

- GitHub Actions の `LINE Notify` ワークフローを手動実行（`workflow_dispatch`）
- または毎時実行（cron設定済み）

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
