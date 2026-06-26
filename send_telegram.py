#!/usr/bin/env python3
"""
텔레그램 봇 메시지 전송
사용법: python3 send_telegram.py "메시지 내용"
"""

import sys
import os
import requests

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8918143605:AAFtJ63hmBuxPM9nfc_hA8SxMzrMAPAWm_Y")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "7526986526")


def send_telegram_message(message: str) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    # 텔레그램 메시지 4096자 제한, 초과 시 분할 전송
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]

    for i, chunk in enumerate(chunks):
        data = {
            "chat_id": CHAT_ID,
            "text": chunk,
            "parse_mode": "HTML",
        }
        try:
            resp = requests.post(url, data=data, timeout=10)
            result = resp.json()
            if result.get("ok"):
                print(f"[OK] 텔레그램 전송 성공 ({i+1}/{len(chunks)})")
            else:
                print(f"[ERROR] 텔레그램 오류: {result}")
                return False
        except requests.exceptions.ConnectionError:
            print("[ERROR] 네트워크 연결 실패 - api.telegram.org allowlist 확인 필요")
            return False
        except Exception as e:
            print(f"[ERROR] 예외: {e}")
            return False

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python3 send_telegram.py '메시지 내용'")
        sys.exit(1)

    success = send_telegram_message(sys.argv[1])
    sys.exit(0 if success else 1)
