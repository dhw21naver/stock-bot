#!/usr/bin/env python3
"""
텔레그램 봇 메시지 전송
사용법: python3 send_telegram.py "메시지 내용"
"""

import sys
import os
import requests

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8918143605:AAFtJ63hmBuxPM9nfc_hA8SxMzrMAPAWm_Y")

# 전송 대상 CHAT_ID 목록 (개인 + 그룹)
CHAT_IDS = [
    os.environ.get("TELEGRAM_CHAT_ID", "7526986526"),  # 개인
    "-1004459717351",  # Stock_Info_DHW 그룹
]


def send_to_chat(chat_id: str, message: str) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]

    for i, chunk in enumerate(chunks):
        data = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
        }
        try:
            resp = requests.post(url, data=data, timeout=10)
            result = resp.json()
            if result.get("ok"):
                print(f"[OK] 전송 성공 → {chat_id} ({i+1}/{len(chunks)})")
            else:
                print(f"[ERROR] {chat_id} 오류: {result}")
                return False
        except requests.exceptions.ConnectionError:
            print("[ERROR] 네트워크 연결 실패 - api.telegram.org allowlist 확인 필요")
            return False
        except Exception as e:
            print(f"[ERROR] 예외: {e}")
            return False
    return True


def send_telegram_message(message: str) -> bool:
    results = [send_to_chat(chat_id, message) for chat_id in CHAT_IDS]
    return all(results)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python3 send_telegram.py '메시지 내용'")
        sys.exit(1)

    success = send_telegram_message(sys.argv[1])
    sys.exit(0 if success else 1)
