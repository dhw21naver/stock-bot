#!/usr/bin/env python3
"""
해외 증시 데이터 수집 (yfinance 우선, 실패 시 Yahoo Finance API 직접 호출)
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# 주요 해외 지수
INDICES = {
    "나스닥": "^IXIC",
    "S&P500": "^GSPC",
    "다우존스": "^DJI",
    "필라반도체(SOX)": "^SOX",
    "러셀2000": "^RUT",
}


def fetch_yfinance(ticker: str) -> dict | None:
    """yfinance로 지수 데이터 조회"""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.fast_info
        return {
            "close": info.last_price,
            "prev_close": info.previous_close,
            "change_val": info.last_price - info.previous_close,
            "change_rate": ((info.last_price - info.previous_close) / info.previous_close) * 100,
        }
    except ImportError:
        return None
    except Exception as e:
        print(f"[yfinance] {ticker} 오류: {e}", file=sys.stderr)
        return None


def fetch_yahoo_api(ticker: str) -> dict | None:
    """Yahoo Finance API 직접 호출 (yfinance 없을 때 폴백)"""
    try:
        import requests
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        params = {
            "interval": "1d",
            "range": "2d",
        }
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        result = data["chart"]["result"][0]
        meta = result["meta"]

        close = meta.get("regularMarketPrice", 0)
        prev_close = meta.get("previousClose", meta.get("chartPreviousClose", 0))
        change_val = close - prev_close
        change_rate = (change_val / prev_close * 100) if prev_close else 0

        return {
            "close": close,
            "prev_close": prev_close,
            "change_val": change_val,
            "change_rate": change_rate,
        }
    except Exception as e:
        print(f"[Yahoo API] {ticker} 오류: {e}", file=sys.stderr)
        return None


def get_index_data(name: str, ticker: str) -> dict:
    """지수 데이터 수집 (yfinance → Yahoo Finance API 순서)"""
    data = fetch_yfinance(ticker)
    if data:
        source = "yfinance"
    else:
        data = fetch_yahoo_api(ticker)
        source = "yahoo_api" if data else "unavailable"

    return {
        "name": name,
        "ticker": ticker,
        "source": source,
        "data": data,
    }


def format_result(results: list) -> str:
    """결과를 카카오톡용 텍스트로 포맷"""
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    lines = [f"[해외증시] 기준: {now_kst}"]

    for r in results:
        name = r["name"]
        d = r.get("data")
        if not d:
            lines.append(f"  {name}: 데이터 없음 (출처: {r['source']})")
            continue

        close = d.get("close", 0)
        change_val = d.get("change_val", 0)
        change_rate = d.get("change_rate", 0)

        if change_val > 0:
            arrow = "▲"
        elif change_val < 0:
            arrow = "▼"
        else:
            arrow = "─"

        lines.append(
            f"  {name}: {close:,.2f} "
            f"{arrow} {change_val:+.2f} ({change_rate:+.2f}%) "
            f"[{r['source']}]"
        )

    return "\n".join(lines)


def main():
    results = []
    for name, ticker in INDICES.items():
        r = get_index_data(name, ticker)
        results.append(r)

    output = {
        "timestamp": datetime.now(KST).isoformat(),
        "market": "GLOBAL",
        "results": results,
        "formatted": format_result(results),
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
