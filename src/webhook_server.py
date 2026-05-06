import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
from typing import Any

import requests
from fastapi import FastAPI, Header, HTTPException, Request

from src.line_client import reply_line_message

ROOT_DIR = Path(__file__).resolve().parent.parent
STOCKS_FILE = ROOT_DIR / "config" / "stocks.txt"
SETTINGS_FILE = ROOT_DIR / "config" / "settings.json"

app = FastAPI()


class ConfigUpdateError(Exception):
    pass


def _line_signature(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _ensure_files() -> None:
    STOCKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not STOCKS_FILE.exists():
        STOCKS_FILE.write_text("", encoding="utf-8")
    if not SETTINGS_FILE.exists():
        SETTINGS_FILE.write_text(
            json.dumps({"change_threshold_percent": 2.0}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )


def _load_symbols() -> list[str]:
    _ensure_files()
    items = []
    for line in STOCKS_FILE.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        items.append(text)
    return items


def _save_symbols(symbols: list[str]) -> None:
    text = "\n".join(symbols)
    if text:
        text += "\n"
    STOCKS_FILE.write_text(text, encoding="utf-8")


def _load_threshold() -> float:
    _ensure_files()
    data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    value = float(data.get("change_threshold_percent", 2.0))
    return max(0.0, value)


def _save_threshold(value: float) -> None:
    _ensure_files()
    SETTINGS_FILE.write_text(
        json.dumps({"change_threshold_percent": max(0.0, value)}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def _github_update_file(path: str, content_text: str, message: str) -> None:
    token = os.getenv("GITHUB_TOKEN_FOR_CONFIG")
    repo = os.getenv("GITHUB_REPOSITORY")
    branch = os.getenv("GITHUB_BRANCH", "main")
    if not token or not repo:
        return

    base_url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    sha = None
    get_res = requests.get(base_url, headers=headers, params={"ref": branch}, timeout=20)
    if get_res.status_code == 200:
        sha = get_res.json().get("sha")
    elif get_res.status_code != 404:
        raise ConfigUpdateError(f"GitHubファイル取得失敗: {get_res.status_code} {get_res.text}")

    payload: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(content_text.encode("utf-8")).decode("utf-8"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    put_res = requests.put(base_url, headers=headers, json=payload, timeout=20)
    if put_res.status_code >= 400:
        raise ConfigUpdateError(f"GitHub更新失敗: {put_res.status_code} {put_res.text}")


def _sync_to_github() -> None:
    _github_update_file(
        "config/stocks.txt",
        STOCKS_FILE.read_text(encoding="utf-8"),
        "Update stocks from LINE command",
    )
    _github_update_file(
        "config/settings.json",
        SETTINGS_FILE.read_text(encoding="utf-8"),
        "Update threshold from LINE command",
    )


def _help_text() -> str:
    return (
        "コマンド一覧\n"
        "追加 7203.T\n"
        "削除 7203.T\n"
        "一覧\n"
        "しきい値 2.0\n"
        "ヘルプ"
    )


def _handle_command(text: str) -> str:
    command = text.strip()
    if not command:
        return _help_text()

    # 全角スペースを含む空白を半角スペースに正規化
    normalized = re.sub(r"\s+", " ", command.replace("\u3000", " ")).strip()
    lower = normalized.lower()

    if normalized in ("一覧", "list"):
        symbols = _load_symbols()
        threshold = _load_threshold()
        if not symbols:
            return f"登録銘柄はありません。\nしきい値: {threshold:.2f}%"
        return "登録銘柄:\n" + "\n".join(symbols) + f"\nしきい値: {threshold:.2f}%"

    if normalized.startswith("追加 ") or lower.startswith("add "):
        symbol = normalized.split(" ", 1)[1].strip().upper()
        if not symbol:
            return "追加する銘柄コードを指定してください。例: 追加 7203.T"
        symbols = _load_symbols()
        if symbol in symbols:
            return f"{symbol} はすでに登録済みです。"
        symbols.append(symbol)
        _save_symbols(symbols)
        _sync_to_github()
        return f"{symbol} を追加しました。"

    if normalized.startswith("削除 ") or lower.startswith("remove "):
        symbol = normalized.split(" ", 1)[1].strip().upper()
        symbols = _load_symbols()
        if symbol not in symbols:
            return f"{symbol} は登録されていません。"
        symbols = [s for s in symbols if s != symbol]
        _save_symbols(symbols)
        _sync_to_github()
        return f"{symbol} を削除しました。"

    if normalized.startswith("しきい値 ") or lower.startswith("threshold "):
        raw = normalized.split(" ", 1)[1].strip()
        try:
            value = float(raw)
        except ValueError:
            return "しきい値は数値で指定してください。例: しきい値 2.0"
        _save_threshold(value)
        _sync_to_github()
        return f"しきい値を {max(0.0, value):.2f}% に更新しました。"

    if normalized in ("ヘルプ", "help"):
        return _help_text()

    return f"コマンドを認識できませんでした: {command}\n" + _help_text()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/callback")
async def callback(
    request: Request,
    x_line_signature: str = Header(default="", alias="X-Line-Signature"),
) -> dict[str, str]:
    secret = os.getenv("LINE_CHANNEL_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="LINE_CHANNEL_SECRET が未設定です。")

    body = await request.body()
    expected = _line_signature(body, secret)
    if not hmac.compare_digest(expected, x_line_signature):
        raise HTTPException(status_code=401, detail="署名検証に失敗しました。")

    payload = json.loads(body.decode("utf-8"))
    for event in payload.get("events", []):
        if event.get("type") != "message":
            continue
        message = event.get("message", {})
        if message.get("type") != "text":
            continue
        reply_token = event.get("replyToken")
        if not reply_token:
            continue
        response_text = _handle_command(message.get("text", ""))
        reply_line_message(reply_token, response_text)

    return {"status": "ok"}
