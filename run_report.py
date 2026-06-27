#!/usr/bin/env python3
"""
주식 & 뉴스 자동 시황 보고 (GitHub Actions 실행용)
1. fetch_krx.py  → 국내 증시
2. fetch_global.py → 해외 증시
3. RSS 피드 → 24h 뉴스 5건 (API 불필요)
4. send_telegram.py → 텔레그램 전송
"""

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import requests

KST = ZoneInfo("Asia/Seoul")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

RSS_FEEDS = [
    ("네이버 금융", "https://finance.naver.com/news/news_list.naver?mode=RSS&section_cd=101"),
    ("연합뉴스 경제", "https://www.yonhapnewstv.co.kr/category/news/economy/feed/"),
    ("한국경제", "https://www.hankyung.com/feed/economy"),
    ("매일경제", "https://www.mk.co.kr/rss/30000001/"),
    ("머니투데이", "https://rss.mt.co.kr/mt_news_economy.xml"),
]


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


def parse_rss_date(date_str: str) -> datetime | None:
    """RSS pubDate 파싱"""
    if not date_str:
        return None
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def fetch_rss_news(max_items: int = 5) -> list[dict]:
    """여러 RSS 피드에서 24시간 이내 뉴스 수집"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    items = []

    headers = {"User-Agent": "Mozilla/5.0 (compatible; StockBot/1.0)"}

    for source, url in RSS_FEEDS:
        if len(items) >= max_items * 2:
            break
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub_date = item.findtext("pubDate") or item.findtext("dc:date", namespaces={"dc": "http://purl.org/dc/elements/1.1/"})
                description = (item.findtext("description") or "").strip()

                if not title or not link:
                    continue

                dt = parse_rss_date(pub_date) if pub_date else None
                if dt and dt < cutoff:
                    continue  # 24시간 이전 뉴스 제외

                # HTML 태그 제거
                import re
                description = re.sub(r"<[^>]+>", "", description)[:100]

                items.append({
                    "source": source,
                    "title": title,
                    "link": link,
                    "pub_date": dt.astimezone(KST).strftime("%Y-%m-%d %H:%M KST") if dt else "시각 미확인",
                    "summary": description or "요약 없음",
                })

        except Exception as e:
            print(f"[RSS] {source} 오류: {e}", file=sys.stderr)
            continue

    # 중복 제거 후 상위 max_items개
    seen = set()
    unique = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
        if len(unique) >= max_items:
            break

    return unique


def build_message(krx_text: str, global_text: str, news_items: list[dict]) -> str:
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    lines = [
        "📊 주식 & 뉴스 시황",
        f"⏰ {now_kst}",
        "",
        "━━━━ 🇰🇷 국내 증시 ━━━━",
    ]

    for line in krx_text.splitlines():
        if line.startswith("["):
            continue
        lines.append(line)

    lines += ["", "━━━━ 🌏 해외 증시 ━━━━"]
    for line in global_text.splitlines():
        if line.startswith("["):
            continue
        lines.append(line)

    lines += ["", "━━━━ 📰 오늘의 핵심 뉴스 ━━━━"]

    if not news_items:
        lines.append("  뉴스를 가져오지 못했습니다.")
    else:
        for i, item in enumerate(news_items, 1):
            lines += [
                f"[{i}] {item['title']}",
                f"    {item['pub_date']} | {item['source']}",
                f"    {item['summary']}",
                f"    🔗 {item['link']}",
                "",
            ]

    lines.append("🤖 Claude 자동 시황 알림")
    return "\n".join(lines)


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

    news_items = fetch_rss_news(5)
    print(f"[OK] 뉴스 {len(news_items)}건 수집 완료")

    message = build_message(krx_text, global_text, news_items)
    print("[OK] 메시지 생성 완료")
    print("--- 미리보기 ---")
    print(message[:300])
    print("...")

    if send_telegram(message):
        print("[OK] 텔레그램 전송 완료")
    else:
        print("[FALLBACK] 텔레그램 전송 실패 — 메시지 전체 출력:")
        print(message)
        sys.exit(1)


if __name__ == "__main__":
    main()
