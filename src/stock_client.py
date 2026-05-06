from dataclasses import dataclass
import time
from typing import List

import requests

YAHOO_QUOTE_API = "https://query1.finance.yahoo.com/v7/finance/quote"
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


def fetch_quotes(symbols: List[str]) -> List[StockQuote]:
    if not symbols:
        raise StockClientError("銘柄が登録されていません。")

    headers = {"User-Agent": "line-stock-notifier/1.0"}
    response: requests.Response | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        response = requests.get(
            YAHOO_QUOTE_API,
            params={"symbols": ",".join(symbols)},
            headers=headers,
            timeout=20,
        )
        if response.status_code != 429:
            break
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_SECONDS * attempt)

    if response is None:
        raise StockClientError("株価取得レスポンスの生成に失敗しました。")

    if response.status_code >= 400:
        raise StockClientError(
            f"株価取得に失敗しました: {response.status_code} {response.text}"
        )

    payload = response.json()
    results = payload.get("quoteResponse", {}).get("result", [])
    if not results:
        raise StockClientError("株価データを取得できませんでした。銘柄コードを確認してください。")

    quotes: List[StockQuote] = []
    for item in results:
        symbol = item.get("symbol")
        if not symbol:
            continue

        price = item.get("regularMarketPrice")
        change = item.get("regularMarketChange")
        change_percent = item.get("regularMarketChangePercent")

        if price is None or change is None or change_percent is None:
            continue

        quotes.append(
            StockQuote(
                symbol=symbol,
                short_name=item.get("shortName", symbol),
                price=float(price),
                change=float(change),
                change_percent=float(change_percent),
                currency=item.get("currency", ""),
            )
        )

    if not quotes:
        raise StockClientError("有効な株価データを生成できませんでした。")

    return quotes
