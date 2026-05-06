import os
from typing import Final

import requests

LINE_PUSH_API: Final[str] = "https://api.line.me/v2/bot/message/push"
LINE_REPLY_API: Final[str] = "https://api.line.me/v2/bot/message/reply"


class LineClientError(Exception):
    pass


def send_line_message(message: str) -> None:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    to = os.getenv("LINE_TO")

    if not token:
        raise LineClientError("環境変数 LINE_CHANNEL_ACCESS_TOKEN が未設定です。")
    if not to:
        raise LineClientError("環境変数 LINE_TO が未設定です。")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    payload = {
        "to": to,
        "messages": [{"type": "text", "text": message}],
    }

    response = requests.post(LINE_PUSH_API, headers=headers, json=payload, timeout=15)
    if response.status_code >= 400:
        raise LineClientError(
            f"LINE送信に失敗しました: {response.status_code} {response.text}"
        )


def reply_line_message(reply_token: str, message: str) -> None:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        raise LineClientError("環境変数 LINE_CHANNEL_ACCESS_TOKEN が未設定です。")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": message}],
    }
    response = requests.post(LINE_REPLY_API, headers=headers, json=payload, timeout=15)
    if response.status_code >= 400:
        raise LineClientError(
            f"LINE返信に失敗しました: {response.status_code} {response.text}"
        )
