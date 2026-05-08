from datetime import datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from stock_client import StockClientError, fetch_quotes


STOCKS_FILE_PATH = Path(__file__).resolve().parent.parent / "config" / "stocks.txt"
SETTINGS_FILE_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.json"


def _now_jst_text() -> str:
    try:
        return datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S JST")
    except ZoneInfoNotFoundError:
        # tzdata 未導入環境でも処理を止めず、ローカル時刻で継続する
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_symbols() -> list[str]:
    """
    銘柄コードを読み込む。環境変数 STOCK_SYMBOLS があれば優先する。
    """
    raw = os.getenv("STOCK_SYMBOLS", "").strip()
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]

    if not STOCKS_FILE_PATH.exists():
        return []

    symbols: list[str] = []
    for line in STOCKS_FILE_PATH.read_text(encoding="utf-8").splitlines():
        symbol = line.strip()
        if not symbol or symbol.startswith("#"):
            continue
        symbols.append(symbol)
    return symbols


def load_threshold_percent() -> float:
    raw = os.getenv("CHANGE_THRESHOLD_PERCENT", "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass

    if SETTINGS_FILE_PATH.exists():
        try:
            data = json.loads(SETTINGS_FILE_PATH.read_text(encoding="utf-8"))
            value = float(data.get("change_threshold_percent", 2.0))
            return max(0.0, value)
        except (ValueError, TypeError, json.JSONDecodeError):
            return 2.0
    return 2.0


def build_message() -> str | None:
    """
    LINEに送る本文を生成する。
    ここだけ差し替えれば、送信内容を自由に変更できる。
    """
    now = _now_jst_text()
    symbols = load_symbols()
    if not symbols:
        return None
    threshold = load_threshold_percent()
    try:
        quotes = fetch_quotes(symbols)
    except StockClientError as exc:
        return f"📈 株価通知\n🕒 {now}\n\n⚠️ 株価の取得に失敗しました。\n{exc}"

    hits = []
    for quote in quotes:
        if abs(quote.change_percent) < threshold:
            continue
        hits.append(quote)

    if not hits:
        return None

    # 変動率が大きい順に並べると重要銘柄を先頭で確認しやすい
    hits.sort(key=lambda q: abs(q.change_percent), reverse=True)

    up_count = sum(1 for q in hits if q.change >= 0)
    down_count = len(hits) - up_count

    lines = [
        "📈 株価通知",
        f"🕒 {now}",
        f"🎯 しきい値: ±{threshold:.2f}% 以上",
        f"🟢 上昇 {up_count} / 🔴 下落 {down_count}",
        "",
    ]

    for quote in hits:
        if quote.change > 0:
            icon = "🟢"
            direction = "▲"
        elif quote.change < 0:
            icon = "🔴"
            direction = "▼"
        else:
            icon = "⚪"
            direction = "→"

        lines.append(
            f"{icon} {quote.symbol} ({quote.short_name})\n"
            f"  現在値: {quote.price:.2f} {quote.currency}\n"
            f"  前日比: {direction} {abs(quote.change):.2f} ({quote.change_percent:+.2f}%)"
        )

    return "\n".join(lines)
