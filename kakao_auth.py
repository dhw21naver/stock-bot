#!/usr/bin/env python3
"""
카카오 액세스 토큰 발급 및 갱신 스크립트
최초 1회 실행하여 access_token 발급 후 .env 파일에 저장
"""

import sys
import os
import requests
import json
from pathlib import Path

ENV_FILE = Path(__file__).parent / ".env"
TOKEN_FILE = Path(__file__).parent / "kakao_token.json"


def load_env():
    """환경변수 파일 로드"""
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"')
    return env


def get_token_via_code(rest_api_key: str, redirect_uri: str, code: str) -> dict:
    """인가 코드로 액세스 토큰 발급"""
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": rest_api_key,
        "redirect_uri": redirect_uri,
        "code": code,
    }
    resp = requests.post(url, data=data, timeout=10)
    resp.raise_for_status()
    return resp.json()


def refresh_token(rest_api_key: str, refresh_token_str: str) -> dict:
    """리프레시 토큰으로 액세스 토큰 갱신"""
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token_str,
    }
    resp = requests.post(url, data=data, timeout=10)
    resp.raise_for_status()
    return resp.json()


def save_tokens(tokens: dict):
    """토큰을 파일에 저장"""
    existing = {}
    if TOKEN_FILE.exists():
        existing = json.loads(TOKEN_FILE.read_text())

    existing.update({k: v for k, v in tokens.items() if v})
    TOKEN_FILE.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
    print(f"[OK] 토큰 저장됨: {TOKEN_FILE}")


def load_tokens() -> dict:
    """저장된 토큰 로드"""
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text())
    return {}


def get_valid_access_token(rest_api_key: str) -> str | None:
    """유효한 액세스 토큰 반환 (만료 시 자동 갱신)"""
    tokens = load_tokens()

    if not tokens.get("access_token"):
        return None

    # 갱신 시도 (리프레시 토큰 있으면)
    if tokens.get("refresh_token"):
        try:
            new_tokens = refresh_token(rest_api_key, tokens["refresh_token"])
            save_tokens(new_tokens)
            return new_tokens.get("access_token") or tokens["access_token"]
        except Exception as e:
            print(f"[WARN] 토큰 갱신 실패: {e}")

    return tokens.get("access_token")


if __name__ == "__main__":
    env = load_env()
    rest_api_key = env.get("KAKAO_REST_API_KEY", "")
    redirect_uri = env.get("KAKAO_REDIRECT_URI", "https://example.com/oauth")

    if not rest_api_key:
        print("=" * 60)
        print("카카오 REST API 키를 .env 파일에 설정하세요:")
        print()
        print("  KAKAO_REST_API_KEY=여기에_REST_API_키_입력")
        print("  KAKAO_REDIRECT_URI=https://example.com/oauth")
        print("=" * 60)
        sys.exit(1)

    print("=" * 60)
    print("카카오 인증 URL을 브라우저에서 열어 로그인 후,")
    print("리다이렉트된 URL의 ?code= 값을 복사하세요.")
    print()
    auth_url = (
        f"https://kauth.kakao.com/oauth/authorize"
        f"?client_id={rest_api_key}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=talk_message"
    )
    print(f"인증 URL:\n{auth_url}")
    print("=" * 60)

    code = input("\n인가 코드 입력 (URL의 code= 값): ").strip()
    if not code:
        print("[ERROR] 코드를 입력하지 않았습니다.")
        sys.exit(1)

    try:
        tokens = get_token_via_code(rest_api_key, redirect_uri, code)
        save_tokens(tokens)
        access_token = tokens.get("access_token")
        print(f"\n[OK] 액세스 토큰 발급 성공!")
        print(f"     access_token: {access_token[:20]}...")

        # .env 에도 저장
        env_content = ENV_FILE.read_text() if ENV_FILE.exists() else ""
        if "KAKAO_ACCESS_TOKEN" not in env_content:
            with open(ENV_FILE, "a") as f:
                f.write(f'\nKAKAO_ACCESS_TOKEN={access_token}\n')
            print(f"[OK] .env 파일에도 저장됨")

    except Exception as e:
        print(f"[ERROR] 토큰 발급 실패: {e}")
        sys.exit(1)
