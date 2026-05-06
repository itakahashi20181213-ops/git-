from message_builder import build_message
from line_client import send_line_message


def main() -> None:
    message = build_message()
    if not message:
        print("しきい値以上の変動がないため送信をスキップしました。")
        return
    send_line_message(message)
    print("LINEへの送信に成功しました。")


if __name__ == "__main__":
    main()
