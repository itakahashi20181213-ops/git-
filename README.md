# LINE送信システム（クラウド実行 / Git運用）

後から通知内容を差し替えできるように、以下の構成で作成しています。

- `src/message_builder.py`: 送る情報を組み立てる場所（今後ここを変更）
- `src/line_client.py`: LINE Messaging APIへ送信
- `src/main.py`: 実行エントリーポイント
- `.github/workflows/line-notify.yml`: GitHub Actions でのクラウド実行設定

## 事前準備（LINE側）

1. LINE Developersで Messaging API のチャネルを作成
2. `Channel access token` を発行
3. 送信先の `userId` / `groupId` / `roomId` を取得（`LINE_TO` として使用）

## GitHub Secrets

このリポジトリの Secrets に以下を登録してください。

- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_TO`

## 実行方法

### クラウド実行（推奨）

- GitHub Actions の `LINE Notify` ワークフローを手動実行（`workflow_dispatch`）
- または毎時実行（cron設定済み）

### ローカル確認

```powershell
pip install -r requirements.txt
$env:LINE_CHANNEL_ACCESS_TOKEN="YOUR_TOKEN"
$env:LINE_TO="YOUR_USER_OR_GROUP_ID"
python src/main.py
```

## 送信内容の変更

今後「何の情報を送るか」が決まったら、`src/message_builder.py` の `build_message()` を置き換えるだけで対応できます。
