#!/usr/bin/env python3
"""
국내 증시 데이터 수집 (pykrx 우선, 실패 시 KRX HTTP API 직접 호출)
pykrx가 없어도 KRX 공식 API를 requests로 직접 호출
"""

import json
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

def get_today_kst() -> str:
    """오늘 날짜 (KST 기준, YYYYMMDD)"""
    now = datetime.now(KST)
    return now.strftime("%Y%m%d")

def get_prev_business_day(date_str: str) -> str:
    """전 영업일 계산 (간단 버전: 주말 건너뜀)"""
    dt = datetime.strptime(date_str, "%Y%m%d")
    delta = 1
    while True:
        prev = dt - timedelta(days=delta)
        if prev.weekday() < 5:  # 월~금
            return prev.strftime("%Y%m%d")
        delta += 1


def fetch_index_pykrx(index_code: str, date_str: str) -> dict | None:
    """pykrx로 지수 데이터 조회"""
    try:
        from pykrx import stock
        df = stock.get_index_ohlcv(date_str, date_str, index_code)
        if df is None or df.empty:
            return None
        row = df.iloc[-1]
        return {
            "close": float(row["종가"]),
            "open": float(row["시가"]),
            "high": float(row["고가"]),
            "low": float(row["저가"]),
            "volume": int(row["거래량"]),
        }
    except ImportError:
        return None
    except Exception as e:
        print(f"[pykrx] 오류: {e}", file=sys.stderr)
        return None


def fetch_index_krx_api(index_code: str, date_str: str) -> dict | None:
    """KRX 공식 HTTP API 직접 호출"""
    try:
        import requests

        url = "http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "http://data.krx.co.kr/",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "bld": "dbms/MDC/STAT/standard/MDCSTAT00301",
            "locale": "ko_KR",
            "tboxindIdx_finder_equityindisu_0": index_code,
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
            "change": float(item.get("FLUC_RT", "0").replace(",", "")),
            "change_val": float(item.get("PRV_DD_CMPR", "0").replace(",", "")),
        }
    except Exception as e:
        print(f"[KRX API] 오류: {e}", file=sys.stderr)
        return None


def get_index_data(name: str, index_code: str, date_str: str, prev_date: str) -> dict:
    """지수 데이터 수집 (pykrx → KRX API 순서로 시도)"""
    data = fetch_index_pykrx(index_code, date_str)
    if data:
        source = "pykrx"
    else:
        data = fetch_index_krx_api(index_code, date_str)
        source = "krx_api" if data else "unavailable"

    return {
        "name": name,
        "code": index_code,
        "date": date_str,
        "source": source,
        "data": data,
    }


def format_result(results: list) -> str:
    """결과를 카카오톡용 텍스트로 포맷"""
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    lines = [f"[국내증시] 기준: {now_kst}"]

    for r in results:
        name = r["name"]
        d = r.get("data")
        if not d:
            lines.append(f"  {name}: 데이터 없음 (출처: {r['source']})")
            continue

        close = d.get("close", 0)
        change_val = d.get("change_val", 0)
        change_rate = d.get("change", 0)

        if change_val > 0:
            arrow = "▲"
        elif change_val < 0:
            arrow = "▼"
            change_val = abs(change_val)
        else:
            arrow = "─"

        lines.append(
            f"  {name}: {close:,.2f} "
            f"{arrow} {change_val:+.2f} ({change_rate:+.2f}%) "
            f"[{r['source']}]"
        )

    return "\n".join(lines)


def main():
    today = get_today_kst()
    prev = get_prev_business_day(today)

    indices = [
        ("코스피", "1001"),
        ("코스닥", "2001"),
        ("코스피200", "1028"),
    ]

    results = []
    for name, code in indices:
        r = get_index_data(name, code, today, prev)
        results.append(r)

    # JSON 출력 (스케줄 작업에서 파싱용)
    output = {
        "timestamp": datetime.now(KST).isoformat(),
        "market": "KRX",
        "results": results,
        "formatted": format_result(results),
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
