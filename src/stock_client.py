from dataclasses import dataclass
import time
from typing import List

import requests

YAHOO_CHART_API = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
MAX_RETRIES = 4
RETRY_SECONDS = 5


@dataclass
class StockQuote:
    symbol: str
    short_name: str
    price: float
    change: float
    change_percent: float
    currency: str


class StockClientError(Exception):
    pass


def _fetch_quote(symbol: str) -> StockQuote:
    headers = {"User-Agent": "line-stock-notifier/1.0"}
    response: requests.Response | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        response = requests.get(
            YAHOO_CHART_API.format(symbol=symbol),
            params={"interval": "1d", "range": "5d"},
            headers=headers,
            timeout=20,
        )
        if response.status_code == 200:
            break

        # 429/5xx は一時的エラーとしてリトライ
        if response.status_code == 429 or response.status_code >= 500:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_SECONDS * attempt)
                continue
        break

    if response is None:
        raise StockClientError(f"{symbol}: 株価取得レスポンスの生成に失敗しました。")

    if response.status_code >= 400:
        raise StockClientError(
            f"{symbol}: 株価取得に失敗しました: {response.status_code} {response.text}"
        )

    payload = response.json()
    result = payload.get("chart", {}).get("result", [])
    if not result:
        error = payload.get("chart", {}).get("error")
        raise StockClientError(f"{symbol}: 株価データを取得できませんでした。{error}")

    meta = result[0].get("meta", {})
    price = meta.get("regularMarketPrice")
    prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
    if price is None:
        raise StockClientError(f"{symbol}: 現在価格を取得できませんでした。")
    if not prev_close:
        prev_close = price

    change = float(price) - float(prev_close)
    change_percent = (change / float(prev_close) * 100.0) if float(prev_close) != 0 else 0.0

    return StockQuote(
        symbol=symbol,
        short_name=meta.get("shortName", symbol),
        price=float(price),
        change=float(change),
        change_percent=float(change_percent),
        currency=meta.get("currency", ""),
    )


def fetch_quotes(symbols: List[str]) -> List[StockQuote]:
    if not symbols:
        raise StockClientError("銘柄が登録されていません。")

    quotes: List[StockQuote] = []
    errors: List[str] = []
    for symbol in symbols:
        try:
            quotes.append(_fetch_quote(symbol))
        except StockClientError as exc:
            errors.append(str(exc))

    if not quotes and errors:
        raise StockClientError(" / ".join(errors))
    if not quotes:
        raise StockClientError("有効な株価データを生成できませんでした。")

    return quotes
