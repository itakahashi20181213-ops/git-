from datetime import datetime
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from stock_client import StockClientError, fetch_quotes


STOCKS_FILE_PATH = Path(__file__).resolve().parent.parent / "config" / "stocks.txt"


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


def build_message() -> str:
    """
    LINEに送る本文を生成する。
    ここだけ差し替えれば、送信内容を自由に変更できる。
    """
    now = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S JST")
    symbols = load_symbols()
    try:
        quotes = fetch_quotes(symbols)
    except StockClientError as exc:
        return f"[株価通知] {now}\n株価の取得に失敗しました。\n{exc}"

    lines = [f"[株価通知] {now}"]
    for quote in quotes:
        sign = "+" if quote.change >= 0 else ""
        lines.append(
            f"{quote.symbol} ({quote.short_name}) {quote.price:.2f} {quote.currency} "
            f"({sign}{quote.change:.2f}, {sign}{quote.change_percent:.2f}%)"
        )
    return "\n".join(lines)
