#!/usr/bin/env python3
# Sell winners on Alpaca every N seconds.
# - Sells any open equity/ETF/crypto position with ≥ +TARGET_PROFIT_PCT gain vs average entry.
# - NEVER sells any symbol in EXCLUDE_SYMBOLS (default: "VIG").
# - Market orders, all out (100% of qty).
# - Logs for Railway.

import os
import time
from datetime import datetime, timezone

from alpaca_trade_api.rest import REST

TARGET_PROFIT_PCT = float(os.getenv("TARGET_PROFIT_PCT", "0.10"))  # 10%
SLEEP_SEC         = int(os.getenv("SLEEP_SEC", "60"))              # how often to poll
EXCLUDE_SYMBOLS   = {s.strip().upper() for s in os.getenv("EXCLUDE_SYMBOLS", "VIG").split(",") if s.strip()}

ALPACA_API_KEY    = os.getenv("ALPACA_API_KEY") or os.getenv("APCA_API_KEY_ID")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY") or os.getenv("APCA_API_SECRET_KEY")
APCA_API_BASE_URL = os.getenv("APCA_API_BASE_URL", "https://api.alpaca.markets")

if not (ALPACA_API_KEY and ALPACA_SECRET_KEY):
    raise RuntimeError("Missing ALPACA_API_KEY / ALPACA_SECRET_KEY (or APCA_* equivalents).")

api = REST(key_id=ALPACA_API_KEY, secret_key=ALPACA_SECRET_KEY, base_url=APCA_API_BASE_URL)

def log(msg: str):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    print(f"[alpaca-sell-winners] {now} | {msg}", flush=True)

def should_sell(position) -> bool:
    try:
        symbol = position.symbol.upper()
        if symbol in EXCLUDE_SYMBOLS:
            log(f"{symbol} | Skipping (excluded).")
            return False
        avg = float(position.avg_entry_price)
        current = float(position.current_price or getattr(position, "asset_current_price", 0) or 0)
        if avg <= 0 or current <= 0:
            log(f"{symbol} | Bad prices avg={avg} current={current}; skip.")
            return False
        gain = (current - avg) / avg
        log(f"{symbol} | avg={avg:.4f} current={current:.4f} gain={gain*100:.2f}%")
        return gain >= TARGET_PROFIT_PCT
    except Exception as e:
        log(f"Error evaluating {getattr(position, 'symbol', '?')}: {e}")
        return False

def sell_all(symbol: str, qty: str):
    try:
        order = api.submit_order(
            symbol=symbol,
            side="sell",
            type="market",
            time_in_force="day",
            qty=qty,
        )
        oid = getattr(order, "id", "") or getattr(order, "client_order_id", "")
        log(f"{symbol} | SELL ALL qty={qty} submitted (order {oid})")
    except Exception as e:
        log(f"{symbol} | SELL failed: {type(e).__name__}: {e}")

def main():
    log(f"Started | target_profit={int(TARGET_PROFIT_PCT*100)}% | exclude={sorted(EXCLUDE_SYMBOLS)} | base={APCA_API_BASE_URL}")
    while True:
        try:
            positions = api.list_positions()
            if not positions:
                log("No open positions.")
            for p in positions:
                if should_sell(p):
                    sell_all(p.symbol, p.qty)
        except Exception as e:
            log(f"Top-level error: {type(e).__name__}: {e}")
        time.sleep(max(5, SLEEP_SEC))

if __name__ == "__main__":
    main()
