#!/usr/bin/env python3
"""
해외 증시 + 환율 + 금리 + 유가 데이터 수집
"""

import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

INDICES = {
    "나스닥":       "^IXIC",
    "S&P500":       "^GSPC",
    "다우존스":     "^DJI",
    "필라반도체":   "^SOX",
    "러셀2000":     "^RUT",
}

EXTRAS = {
    "원/달러 환율":  "USDKRW=X",
    "미국채 10년":   "^TNX",
    "WTI 유가":      "CL=F",
    "금":            "GC=F",
    "VIX 공포지수":  "^VIX",
    "달러/엔":       "JPY=X",
}

# 개별 종목
STOCKS = {
    "삼성전자":   "005930.KS",
    "SK하이닉스": "000660.KS",
    "TSLA":       "TSLA",
    "NVDA":       "NVDA",
    "MSFT":       "MSFT",
}


def fetch_yfinance(ticker: str) -> dict | None:
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.fast_info
        close = info.last_price
        prev = info.previous_close
        if not close or not prev:
            return None
        return {
            "close": close,
            "change_val": close - prev,
            "change_rate": ((close - prev) / prev) * 100,
        }
    except ImportError:
        return None
    except Exception as e:
        print(f"[yfinance] {ticker} 오류: {e}", file=sys.stderr)
        return None


def fetch_yahoo_api(ticker: str) -> dict | None:
    try:
        import requests
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, params={"interval": "1d", "range": "2d"}, timeout=10)
        resp.raise_for_status()
        meta = resp.json()["chart"]["result"][0]["meta"]
        close = meta.get("regularMarketPrice", 0)
        prev = meta.get("previousClose", meta.get("chartPreviousClose", 0))
        if not close or not prev:
            return None
        return {
            "close": close,
            "change_val": close - prev,
            "change_rate": ((close - prev) / prev) * 100,
        }
    except Exception as e:
        print(f"[Yahoo API] {ticker} 오류: {e}", file=sys.stderr)
        return None


def get_data(name: str, ticker: str) -> dict:
    data = fetch_yfinance(ticker) or fetch_yahoo_api(ticker)
    return {
        "name": name,
        "ticker": ticker,
        "source": "yfinance" if data else "unavailable",
        "data": data,
    }


def fmt_line(r: dict, is_currency: bool = False, is_rate: bool = False) -> str:
    name = r["name"]
    d = r.get("data")
    if not d:
        return f"  {name}: 데이터 없음"

    close = d["close"]
    change_val = d["change_val"]
    change_rate = d["change_rate"]
    arrow = "▲" if change_val > 0 else ("▼" if change_val < 0 else "─")

    if is_currency:
        return f"  {name}: {close:,.1f} {arrow} {abs(change_val):.1f} ({change_rate:+.2f}%)"
    elif is_rate:
        return f"  {name}: {close:.2f}% {arrow} {abs(change_val):.2f}%p"
    elif close > 1000:
        return f"  {name}: {close:,.2f} {arrow} {abs(change_val):,.2f} ({change_rate:+.2f}%)"
    else:
        return f"  {name}: {close:.2f} {arrow} {abs(change_val):.2f} ({change_rate:+.2f}%)"


def format_result(indices: list, extras: list, stocks: list) -> str:
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    lines = [f"[해외증시] 기준: {now_kst}"]

    lines.append("  [지수]")
    for r in indices:
        lines.append(fmt_line(r))

    lines.append("  [거시경제]")
    for r in extras:
        is_currency = "환율" in r["name"] or "엔" in r["name"]
        is_rate = "금리" in r["name"] or "국채" in r["name"]
        lines.append(fmt_line(r, is_currency=is_currency, is_rate=is_rate))

    lines.append("  [주요종목]")
    for r in stocks:
        lines.append(fmt_line(r))

    return "\n".join(lines)


def main():
    indices = [get_data(n, t) for n, t in INDICES.items()]
    extras = [get_data(n, t) for n, t in EXTRAS.items()]
    stocks = [get_data(n, t) for n, t in STOCKS.items()]

    output = {
        "timestamp": datetime.now(KST).isoformat(),
        "market": "GLOBAL",
        "results": indices + extras + stocks,
        "formatted": format_result(indices, extras, stocks),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
