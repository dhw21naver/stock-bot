#!/usr/bin/env python3
"""
주식 & 뉴스 자동 시황 보고 (GitHub Actions 실행용)
1. fetch_krx.py  → 국내 증시
2. fetch_global.py → 해외 증시
3. Claude API (web_search) → 24h 뉴스 5건
4. send_telegram.py → 텔레그램 전송
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic

KST = ZoneInfo("Asia/Seoul")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_script(script: str) -> dict | None:
    path = os.path.join(SCRIPT_DIR, script)
    try:
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        print(f"[ERROR] {script}: {e}", file=sys.stderr)
    return None


def fetch_news_via_claude(krx_text: str, global_text: str) -> str:
    """Claude API + web_search로 24시간 뉴스 5건 수집 및 메시지 전체 생성"""
    client = anthropic.Anthropic()
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    system = (
        "너는 주식 시황 분석가야. "
        "주어진 증시 데이터와 웹 검색으로 수집한 최신 뉴스를 바탕으로 "
        "텔레그램 시황 메시지를 작성해. "
        "HTML 태그 없이 순수 텍스트로 작성하고 총 3800자 이내로 제한해."
    )

    user = f"""현재 시각: {now_kst}

[국내 증시 데이터]
{krx_text}

[해외 증시 데이터]
{global_text}

지시사항:
1. web_search 도구로 아래 3가지 검색어로 지난 24시간 뉴스를 검색해:
   - "코스피 코스닥 증시 뉴스"
   - "나스닥 미국증시 뉴스"
   - "반도체 AI 주식 뉴스"
2. 발행 24시간 이내인 핵심 뉴스 5건을 선별해.
3. 아래 형식으로 텔레그램 메시지를 완성해:

📊 주식 & 뉴스 시황
⏰ {now_kst}

━━━━ 🇰🇷 국내 증시 ━━━━
[국내증시 데이터를 지수/등락폭/등락률 형식으로 정리]

━━━━ 🌏 해외 증시 ━━━━
[해외증시 데이터를 지수/등락폭/등락률 형식으로 정리]

━━━━ 📰 오늘의 핵심 뉴스 ━━━━
[1] 제목
    시각 | 호재/중립/악재
    100자 이내 요약
    🔗 링크

[2]~[5] 동일 형식

🤖 Claude 자동 시황 알림
"""

    tools = [{"type": "web_search_20260209", "name": "web_search"}]

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=system,
        tools=tools,
        messages=[{"role": "user", "content": user}],
    )

    # 최종 텍스트 블록 추출
    text_parts = []
    for block in response.content:
        if hasattr(block, "type") and block.type == "text":
            text_parts.append(block.text)

    return "\n".join(text_parts).strip()


def send_telegram(message: str) -> bool:
    script = os.path.join(SCRIPT_DIR, "send_telegram.py")
    try:
        result = subprocess.run(
            [sys.executable, script, message],
            capture_output=True, text=True, timeout=30
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"[ERROR] send_telegram: {e}", file=sys.stderr)
        return False


def main():
    print(f"[START] {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}")

    # 증시 데이터 수집
    krx = run_script("fetch_krx.py")
    krx_text = krx["formatted"] if krx else "국내 증시 데이터 수집 실패"

    glb = run_script("fetch_global.py")
    global_text = glb["formatted"] if glb else "해외 증시 데이터 수집 실패"

    print("[OK] 증시 데이터 수집 완료")

    # Claude API로 뉴스 수집 및 메시지 생성
    message = fetch_news_via_claude(krx_text, global_text)
    print("[OK] 메시지 생성 완료")
    print("--- 메시지 미리보기 ---")
    print(message[:500])
    print("...")

    # 텔레그램 전송
    if send_telegram(message):
        print("[OK] 텔레그램 전송 완료")
    else:
        print("[FALLBACK] 텔레그램 전송 실패 — 메시지 전체 출력:")
        print(message)
        sys.exit(1)


if __name__ == "__main__":
    main()
