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
from src.stock_client import StockClientError, fetch_quotes

ROOT_DIR = Path(__file__).resolve().parent.parent
STOCKS_FILE = ROOT_DIR / "config" / "stocks.txt"
SETTINGS_FILE = ROOT_DIR / "config" / "settings.json"

app = FastAPI()
PENDING_ACTIONS: dict[str, str] = {}


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
        "追加（次のメッセージで銘柄コード）\n"
        "削除（次のメッセージで銘柄コード）\n"
        "株価（次のメッセージで銘柄コード）\n"
        "追加 7203.T\n"
        "削除 7203.T\n"
        "株価 7203.T\n"
        "一覧\n"
        "しきい値 2.0\n"
        "キャンセル\n"
        "ヘルプ"
    )


def _add_symbol(symbol: str) -> str:
    symbols = _load_symbols()
    if symbol in symbols:
        return f"{symbol} はすでに登録済みです。"
    symbols.append(symbol)
    _save_symbols(symbols)
    _sync_to_github()
    return f"{symbol} を追加しました。"


def _remove_symbol(symbol: str) -> str:
    symbols = _load_symbols()
    if symbol not in symbols:
        return f"{symbol} は登録されていません。"
    symbols = [s for s in symbols if s != symbol]
    _save_symbols(symbols)
    _sync_to_github()
    return f"{symbol} を削除しました。"


def _quote_text(symbol: str) -> str:
    try:
        quotes = fetch_quotes([symbol])
    except StockClientError as exc:
        return f"{symbol} の株価取得に失敗しました。\n{exc}"

    quote = quotes[0]
    if quote.change > 0:
        direction = "▲"
    elif quote.change < 0:
        direction = "▼"
    else:
        direction = "→"

    return (
        f"株価: {quote.symbol} ({quote.short_name})\n"
        f"現在値: {quote.price:.2f} {quote.currency}\n"
        f"前日比: {direction} {abs(quote.change):.2f} ({quote.change_percent:+.2f}%)"
    )


def _source_key(event: dict[str, Any]) -> str:
    source = event.get("source", {})
    source_type = source.get("type", "unknown")
    source_id = (
        source.get("userId")
        or source.get("groupId")
        or source.get("roomId")
        or "unknown"
    )
    return f"{source_type}:{source_id}"


def _handle_command(text: str, source_key: str) -> str:
    command = text.strip()
    if not command:
        return _help_text()

    # 全角スペースを含む空白を半角スペースに正規化
    normalized = re.sub(r"\s+", " ", command.replace("\u3000", " ")).strip()
    lower = normalized.lower()

    if normalized in ("キャンセル", "cancel"):
        PENDING_ACTIONS.pop(source_key, None)
        return "入力待ちをキャンセルしました。"

    pending = PENDING_ACTIONS.get(source_key)
    if pending == "add_symbol":
        PENDING_ACTIONS.pop(source_key, None)
        symbol = normalized.upper()
        if " " in symbol:
            return "銘柄コードのみを送信してください。例: 7203.T"
        return _add_symbol(symbol)
    if pending == "remove_symbol":
        PENDING_ACTIONS.pop(source_key, None)
        symbol = normalized.upper()
        if " " in symbol:
            return "銘柄コードのみを送信してください。例: 7203.T"
        return _remove_symbol(symbol)
    if pending == "quote_symbol":
        PENDING_ACTIONS.pop(source_key, None)
        symbol = normalized.upper()
        if " " in symbol:
            return "銘柄コードのみを送信してください。例: 7203.T"
        return _quote_text(symbol)

    if normalized in ("一覧", "list"):
        symbols = _load_symbols()
        threshold = _load_threshold()
        if not symbols:
            return f"登録銘柄はありません。\nしきい値: {threshold:.2f}%"
        return "登録銘柄:\n" + "\n".join(symbols) + f"\nしきい値: {threshold:.2f}%"

    if normalized in ("追加", "add"):
        PENDING_ACTIONS[source_key] = "add_symbol"
        return "追加する銘柄コードを送信してください。例: 7203.T"
    if normalized in ("削除", "remove"):
        PENDING_ACTIONS[source_key] = "remove_symbol"
        return "削除する銘柄コードを送信してください。例: 7203.T"
    if normalized in ("株価", "price"):
        PENDING_ACTIONS[source_key] = "quote_symbol"
        return "確認する銘柄コードを送信してください。例: 7203.T"

    if normalized.startswith("追加 ") or lower.startswith("add "):
        symbol = normalized.split(" ", 1)[1].strip().upper()
        if not symbol:
            return "追加する銘柄コードを指定してください。例: 追加 7203.T"
        return _add_symbol(symbol)

    if normalized.startswith("削除 ") or lower.startswith("remove "):
        symbol = normalized.split(" ", 1)[1].strip().upper()
        if not symbol:
            return "削除する銘柄コードを指定してください。例: 削除 7203.T"
        return _remove_symbol(symbol)
    if normalized.startswith("株価 ") or lower.startswith("price "):
        symbol = normalized.split(" ", 1)[1].strip().upper()
        if not symbol:
            return "確認する銘柄コードを指定してください。例: 株価 7203.T"
        return _quote_text(symbol)

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


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "message": "line webhook server running"}


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
        response_text = _handle_command(message.get("text", ""), _source_key(event))
        reply_line_message(reply_token, response_text)

    return {"status": "ok"}
