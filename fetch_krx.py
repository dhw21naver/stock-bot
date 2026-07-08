#!/usr/bin/env python3
"""
국내 증시 데이터 수집 (네이버 금융 우선, 실패 시 KRX API)
오늘 데이터 없으면 전일 마감 데이터 자동 폴백
"""

import json
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

KST = ZoneInfo("Asia/Seoul")

NAVER_CODE = {
    "코스피":    "0001",
    "코스닥":    "1001",
    "코스피200": "2001",
}

KRX_CODE = {
    "코스피":    "1001",
    "코스닥":    "2001",
    "코스피200": "1028",
}


def fetch_naver(name: str) -> dict | None:
    """네이버 모바일 API - 당일/전일 자동 폴백"""
    try:
        code = NAVER_CODE[name]
        url = f"https://m.stock.naver.com/api/index/{code}/basic"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://m.stock.naver.com",
        }
        resp = requests.get(url, headers=headers, timeout=8)
        resp.raise_for_status()
        data = resp.json()

        close = float(str(data.get("closePrice", "0")).replace(",", ""))
        change_val = float(str(data.get("compareToPreviousClosePrice", "0")).replace(",", ""))
        change_rate = float(str(data.get("fluctuationsRatio", "0")).replace(",", ""))

        if close == 0:
            return None

        return {
            "close": close,
            "change_val": change_val,
            "change_rate": change_rate,
        }
    except Exception as e:
        print(f"[Naver] {name} 오류: {e}", file=sys.stderr)
        return None


def fetch_naver_history(name: str) -> dict | None:
    """네이버 일별 시세 API - 최근 거래일 데이터 가져오기"""
    try:
        code = NAVER_CODE[name]
        url = f"https://m.stock.naver.com/api/index/{code}/price"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://m.stock.naver.com",
        }
        params = {"pageSize": 2, "pageIndex": 1}
        resp = requests.get(url, headers=headers, params=params, timeout=8)
        resp.raise_for_status()
        items = resp.json()

        if not items or len(items) < 1:
            return None

        latest = items[0]
        close = float(str(latest.get("closePrice", "0")).replace(",", ""))
        prev_close = float(str(items[1].get("closePrice", "0")).replace(",", "")) if len(items) > 1 else 0

        if close == 0:
            return None

        change_val = close - prev_close if prev_close else 0
        change_rate = (change_val / prev_close * 100) if prev_close else 0

        return {
            "close": close,
            "change_val": change_val,
            "change_rate": change_rate,
            "date": latest.get("localTradedAt", ""),
        }
    except Exception as e:
        print(f"[Naver History] {name} 오류: {e}", file=sys.stderr)
        return None


def fetch_krx_api(name: str, date_str: str) -> dict | None:
    """KRX 공식 HTTP API"""
    try:
        index_code = KRX_CODE[name]
        url = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "http://data.krx.co.kr/",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "bld": "dbms/MDC/STAT/standard/MDCSTAT00301",
            "locale": "ko_KR",
            "indIdx": index_code,
            "indIdx2": "",
            "strtDd": date_str,
            "endDd": date_str,
            "share": "1",
            "money": "1",
            "csvxls_isNo": "false",
        }
        resp = requests.post(url, headers=headers, data=data, timeout=8)
        result = resp.json()
        items = result.get("output", [])
        if not items:
            return None
        item = items[0]
        return {
            "close": float(item.get("CLSPRC_IDX", "0").replace(",", "")),
            "change_val": float(item.get("PRV_DD_CMPR", "0").replace(",", "")),
            "change_rate": float(item.get("FLUC_RT", "0").replace(",", "")),
        }
    except Exception as e:
        print(f"[KRX API] {name} {date_str} 오류: {e}", file=sys.stderr)
        return None


def get_prev_business_days(n: int = 3) -> list[str]:
    """최근 n개 영업일 날짜 반환 (오늘 포함)"""
    now = datetime.now(KST)
    dates = []
    dt = now
    while len(dates) < n:
        if dt.weekday() < 5:
            dates.append(dt.strftime("%Y%m%d"))
        dt -= timedelta(days=1)
    return dates


def format_result(results: list) -> str:
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    lines = [f"[국내증시] 기준: {now_kst}"]

    for r in results:
        name = r["name"]
        d = r.get("data")
        if not d:
            lines.append(f"  {name}: 데이터 없음")
            continue

        close = d.get("close", 0)
        change_val = d.get("change_val", 0)
        change_rate = d.get("change_rate", 0)
        date_label = f" ({d['date']})" if d.get("date") else ""

        arrow = "▲" if change_val > 0 else ("▼" if change_val < 0 else "─")
        lines.append(
            f"  {name}: {close:,.2f} {arrow} {abs(change_val):.2f} ({change_rate:+.2f}%){date_label} [{r['source']}]"
        )

    return "\n".join(lines)


def main():
    indices = ["코스피", "코스닥", "코스피200"]
    results = []
    dates = get_prev_business_days(3)

    for name in indices:
        # 1순위: 네이버 실시간
        data = fetch_naver(name)
        source = "naver"

        # 2순위: 네이버 일별 시세 (최근 거래일)
        if not data:
            data = fetch_naver_history(name)
            source = "naver_history"

        # 3순위: KRX API (최근 3일 시도)
        if not data:
            for date_str in dates:
                data = fetch_krx_api(name, date_str)
                if data:
                    data["date"] = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                    source = f"krx_{date_str}"
                    break

        if not data:
            source = "unavailable"

        results.append({"name": name, "source": source, "data": data})

    output = {
        "timestamp": datetime.now(KST).isoformat(),
        "market": "KRX",
        "results": results,
        "formatted": format_result(results),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
