#!/usr/bin/env python3
"""
주식 & 뉴스 자동 시황 보고 (GitHub Actions 실행용)
1. fetch_krx.py    → 국내 증시 + 개별종목
2. fetch_global.py → 해외 증시 + 환율 + 금리 + 유가 + 개별종목
3. Claude API      → 뉴스 수집 + 총평 작성
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
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        print(f"[ERROR] {script}: {e}", file=sys.stderr)
    return None


def generate_report_via_claude(krx_text: str, global_text: str) -> str:
    """Claude API로 뉴스 수집 + 총평 포함 메시지 생성"""
    client = anthropic.Anthropic()
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    system = (
        "너는 전문 주식 시황 분석가야. "
        "주어진 증시 데이터를 분석하고, 웹 검색으로 최신 뉴스를 수집해서 "
        "텔레그램 시황 메시지를 작성해. "
        "HTML 태그 없이 순수 텍스트로 작성하고 총 3500자 이내로 제한해."
    )

    user = f"""현재 시각: {now_kst}

[국내 증시 데이터]
{krx_text}

[해외 증시 + 환율 + 금리 + 유가 + 개별종목 데이터]
{global_text}

지시사항:
1. web_search로 아래 4가지를 지난 24시간 기준으로 검색해:
   - "코스피 코스닥 증시 뉴스"
   - "나스닥 미국증시 뉴스"
   - "반도체 AI 주식 뉴스"
   - "오늘 핫한 테마주 섹터 뉴스"

2. 24시간 이내 핵심 뉴스 5건 선별

3. 아래 형식으로 완성된 텔레그램 메시지를 작성해:

📊 주식 & 뉴스 시황
⏰ {now_kst}

━━━━ 🇰🇷 국내 증시 ━━━━
코스피   : [지수] [▲/▼] [등락폭] ([등락률]%)
코스닥   : [지수] [▲/▼] [등락폭] ([등락률]%)
코스피200: [지수] [▲/▼] [등락폭] ([등락률]%)

[개별종목]
삼성전자 : [가격]원 [▲/▼] [등락폭] ([등락률]%)
SK하이닉스: [가격]원 [▲/▼] [등락폭] ([등락률]%)

━━━━ 🌏 해외 증시 ━━━━
나스닥   : [지수] [▲/▼] [등락폭] ([등락률]%)
S&P500   : [지수] [▲/▼] [등락폭] ([등락률]%)
다우존스 : [지수] [▲/▼] [등락폭] ([등락률]%)
필라반도체: [지수] [▲/▼] [등락폭] ([등락률]%)

━━━━ 🌐 거시경제 ━━━━
원/달러  : [환율]원 [▲/▼] [등락폭]
미국채10년: [금리]% [▲/▼] [등락폭]%p
WTI유가  : $[가격] [▲/▼] [등락폭]
금       : $[가격] [▲/▼] [등락폭]

[주요종목]
TSLA : $[가격] ([등락률]%)
NVDA : $[가격] ([등락률]%)
MSFT : $[가격] ([등락률]%)

━━━━ 📰 오늘의 핵심 뉴스 ━━━━
[1] 제목
    시각 | 호재/중립/악재
    100자 요약
    🔗 링크

[2]~[5] 동일 형식

━━━━ 🔥 오늘의 테마 & 섹터 흐름 ━━━━
[오늘 가장 뜨거운 테마 1~2개를 파악하고, 그 파급 연결고리를 분석해줘]
예시 형식:
🌊 메인 테마: [테마명] (예: AI 인프라 확장)
→ 1차 수혜: [산업/종목] - [이유]
→ 2차 수혜: [산업/종목] - [이유]
→ 주목할 리스크: [역풍 요인]

━━━━ 💡 오늘의 시황 총평 ━━━━
[전체 데이터와 뉴스를 종합해서 3~4줄로 오늘 시장 핵심 포인트 총평]
(투자 권유 표현 금지, 사실 기반 분석만)

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

    text_parts = [block.text for block in response.content if hasattr(block, "type") and block.type == "text"]
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

    krx = run_script("fetch_krx.py")
    krx_text = krx["formatted"] if krx else "국내 증시 데이터 수집 실패"

    glb = run_script("fetch_global.py")
    global_text = glb["formatted"] if glb else "해외 증시 데이터 수집 실패"

    print("[OK] 증시 데이터 수집 완료")

    message = generate_report_via_claude(krx_text, global_text)
    print("[OK] 메시지 생성 완료")
    print("--- 미리보기 ---")
    print(message[:500])
    print("...")

    if send_telegram(message):
        print("[OK] 텔레그램 전송 완료")
    else:
        print("[FALLBACK] 텔레그램 전송 실패 — 메시지 전체 출력:")
        print(message)
        sys.exit(1)


if __name__ == "__main__":
    main()
