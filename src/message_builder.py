from datetime import datetime
from zoneinfo import ZoneInfo


def build_message() -> str:
    """
    LINEに送る本文を生成する。
    ここだけ差し替えれば、送信内容を自由に変更できる。
    """
    now = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S JST")
    return f"[通知テスト] クラウド実行OK: {now}"
