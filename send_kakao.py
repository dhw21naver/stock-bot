#!/usr/bin/env python3
"""
카카오톡 나에게 보내기 전송 스크립트
사용법: python3 send_kakao.py "메시지 내용"
- access_token 만료 시 refresh_token으로 자동 갱신
"""

import sys
import os
import re
import requests
import json

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kakao_token.json")


def load_env() -> dict:
    """Load key=value pairs from .env file."""
    env = {}
    try:
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


def save_env_value(key: str, value: str):
    """Update a single key in .env file in-place."""
    try:
        with open(ENV_FILE, "r") as f:
            content = f.read()

        pattern = rf"^{re.escape(key)}=.*$"
        replacement = f"{key}={value}"
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

        if key not in new_content:
            new_content += f"\n{key}={value}\n"

        with open(ENV_FILE, "w") as f:
            f.write(new_content)
    except Exception as e:
        print(f"[WARN] .env 업데이트 실패: {e}")


def save_token_json(access_token: str, refresh_token: str = None):
    """Save updated tokens to kakao_token.json."""
    try:
        try:
            with open(TOKEN_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}

        data["access_token"] = access_token
        if refresh_token:
            data["refresh_token"] = refresh_token

        with open(TOKEN_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] kakao_token.json 업데이트 실패: {e}")


def refresh_access_token(refresh_token: str, rest_api_key: str) -> str | None:
    """refresh_token으로 새 access_token 발급."""
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token,
    }
    try:
        resp = requests.post(url, data=data, timeout=10)
        result = resp.json()
        if "access_token" in result:
            new_access = result["access_token"]
            new_refresh = result.get("refresh_token", refresh_token)  # 새 refresh_token 있으면 갱신
            print(f"[OK] access_token 갱신 성공")
            # 파일에 저장
            save_env_value("KAKAO_ACCESS_TOKEN", new_access)
            if new_refresh != refresh_token:
                save_env_value("KAKAO_REFRESH_TOKEN", new_refresh)
            save_token_json(new_access, new_refresh if new_refresh != refresh_token else None)
            return new_access
        else:
            print(f"[ERROR] 토큰 갱신 실패: {result}")
            return None
    except Exception as e:
        print(f"[ERROR] 토큰 갱신 중 예외: {e}")
        return None


def _do_send(message: str, access_token: str) -> tuple[bool, int]:
    """실제 전송 시도. (성공여부, HTTP 상태코드) 반환."""
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    template = {
        "object_type": "text",
        "text": message[:2000],
        "link": {
            "web_url": "https://finance.naver.com",
            "mobile_web_url": "https://finance.naver.com",
        },
    }
    data = {"template_object": json.dumps(template, ensure_ascii=False)}

    try:
        resp = requests.post(url, headers=headers, data=data, timeout=10)
        if resp.status_code == 200:
            result = resp.json()
            if result.get("result_code") == 0:
                return True, 200
            else:
                print(f"[ERROR] 카카오 응답 오류: {result}")
                return False, 200
        else:
            print(f"[ERROR] HTTP {resp.status_code}: {resp.text}")
            return False, resp.status_code
    except requests.exceptions.ConnectionError:
        print("[ERROR] 네트워크 연결 실패 - kapi.kakao.com allowlist를 확인하세요.")
        return False, 0
    except Exception as e:
        print(f"[ERROR] 예외 발생: {e}")
        return False, -1


def send_kakao_message(message: str) -> bool:
    """카카오톡 나에게 보내기 (access_token 만료 시 자동 갱신)."""
    # .env에서 토큰 로드 (환경변수보다 .env 파일 우선 — 갱신된 값 반영)
    env = load_env()
    access_token = env.get("KAKAO_ACCESS_TOKEN") or os.environ.get("KAKAO_ACCESS_TOKEN", "")
    refresh_token = env.get("KAKAO_REFRESH_TOKEN") or os.environ.get("KAKAO_REFRESH_TOKEN", "")
    rest_api_key = env.get("KAKAO_REST_API_KEY") or os.environ.get("KAKAO_REST_API_KEY", "")

    if not access_token:
        print("[ERROR] KAKAO_ACCESS_TOKEN이 없습니다.")
        return False

    # 1차 전송 시도
    ok, status = _do_send(message, access_token)
    if ok:
        print("[OK] 카카오톡 전송 성공")
        return True

    # 401 (토큰 만료) → refresh
    if status == 401 and refresh_token and rest_api_key:
        print("[INFO] access_token 만료 — 갱신 시도 중...")
        new_token = refresh_access_token(refresh_token, rest_api_key)
        if new_token:
            ok2, _ = _do_send(message, new_token)
            if ok2:
                print("[OK] 토큰 갱신 후 카카오톡 전송 성공")
                return True
            else:
                print("[ERROR] 갱신 후에도 전송 실패")
                return False
        else:
            print("[ERROR] 토큰 갱신 실패")
            return False

    return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python3 send_kakao.py '메시지 내용'")
        sys.exit(1)

    message = sys.argv[1]
    success = send_kakao_message(message)
    sys.exit(0 if success else 1)
