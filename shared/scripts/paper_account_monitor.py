#!/usr/bin/env python3
"""
paper_account_monitor.py
Deterministic paper trading account monitor. No LLM.
Pulls Alpaca paper account: balance, positions, orders, realized/unrealized PnL.
Runs every 15-30 min via cron. Writes snapshot + daily PnL summary.

Outputs:
  memory/paper_account_snapshot.json
  memory/paper_pnl_daily.md
"""
import json, os, time, urllib.request, urllib.error
from datetime import datetime, timezone, date

WS            = os.path.expanduser('~/.openclaw/workspace')
SNAPSHOT_PATH = os.path.join(WS, 'memory/paper_account_snapshot.json')
PNL_PATH      = os.path.join(WS, 'memory/paper_pnl_daily.md')
HISTORY_PATH  = os.path.join(WS, 'memory/paper_pnl_history.json')

PAPER_BASE = 'https://paper-api.alpaca.markets'
DATA_BASE  = 'https://data.alpaca.markets'


def _key():
    k = open(os.path.expanduser('~/.openclaw/secrets/alpaca_paper_key.txt')).read().strip()
    s = open(os.path.expanduser('~/.openclaw/secrets/alpaca_paper_secret.txt')).read().strip()
    return k, s


def _get(base, endpoint, params=''):
    k, s = _key()
    url = base + endpoint + (('?' + params) if params else '')
    req = urllib.request.Request(url, headers={
        'APCA-API-KEY-ID': k, 'APCA-API-SECRET-KEY': s
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def fetch_account():
    return _get(PAPER_BASE, '/v2/account')


def fetch_positions():
    return _get(PAPER_BASE, '/v2/positions')


def fetch_orders(status='all', limit=20):
    return _get(PAPER_BASE, '/v2/orders', f'status={status}&limit={limit}&direction=desc')


def fetch_portfolio_history():
    """Get today's portfolio history for PnL curve."""
    try:
        return _get(PAPER_BASE, '/v2/account/portfolio/history',
                    'period=1D&timeframe=15Min&extended_hours=true')
    except Exception as e:
        return {"error": str(e)}


def build_snapshot():
    now    = datetime.now(timezone.utc)
    now_s  = now.isoformat()
    today  = date.today().isoformat()

    snap = {
        "as_of":     now_s,
        "broker":    "alpaca_paper",
        "account":   {},
        "positions": [],
        "orders":    {"open": [], "filled_today": []},
        "pnl":       {},
        "errors":    [],
    }

    # Account
    try:
        acct = fetch_account()
        snap["account"] = {
            "status":          acct["status"],
            "equity":          float(acct["equity"]),
            "cash":            float(acct["cash"]),
            "portfolio_value": float(acct["portfolio_value"]),
            "buying_power":    float(acct["buying_power"]),
            "currency":        acct.get("currency", "USD"),
            "pattern_day_trader": acct.get("pattern_day_trader", False),
        }
    except Exception as e:
        snap["errors"].append(f"account: {e}")

    # Positions
    try:
        positions = fetch_positions()
        for p in positions:
            snap["positions"].append({
                "symbol":         p["symbol"],
                "qty":            float(p["qty"]),
                "side":           p["side"],
                "avg_entry_price": float(p.get("avg_entry_price", 0)),
                "current_price":  float(p.get("current_price", 0)),
                "cost_basis":     float(p.get("cost_basis", 0)),
                "market_value":   float(p.get("market_value", 0)),
                "unrealized_pl":  float(p.get("unrealized_pl", 0)),
                "unrealized_plpc": float(p.get("unrealized_plpc", 0)),
            })
    except Exception as e:
        snap["errors"].append(f"positions: {e}")

    # Orders
    try:
        orders_open = fetch_orders(status='open', limit=20)
        for o in orders_open:
            snap["orders"]["open"].append({
                "id":     o["id"],
                "symbol": o["symbol"],
                "side":   o["side"],
                "type":   o["type"],
                "qty":    o.get("qty"),
                "status": o["status"],
                "submitted_at": o.get("submitted_at",""),
            })
    except Exception as e:
        snap["errors"].append(f"open_orders: {e}")

    try:
        orders_filled = fetch_orders(status='closed', limit=20)
        today_fills = []
        for o in orders_filled:
            if o.get("status") == "filled":
                filled_at = o.get("filled_at", "")
                if filled_at and filled_at[:10] == today:
                    today_fills.append({
                        "symbol": o["symbol"],
                        "side":   o["side"],
                        "filled_qty": float(o.get("filled_qty", 0)),
                        "filled_avg_price": float(o.get("filled_avg_price") or 0),
                        "filled_at": filled_at,
                    })
        snap["orders"]["filled_today"] = today_fills
    except Exception as e:
        snap["errors"].append(f"filled_orders: {e}")

    # PnL summary
    try:
        total_unrealized = sum(p["unrealized_pl"] for p in snap["positions"])
        equity    = snap["account"].get("equity", 0)
        cash      = snap["account"].get("cash", 0)
        port_val  = snap["account"].get("portfolio_value", 0)
        start_eq  = 100000.0  # paper account start value

        # Try portfolio history for realized PnL today
        ph = fetch_portfolio_history()
        realized_today = "N/A"
        if "equity" in ph and ph["equity"]:
            eq_list = ph["equity"]
            if len(eq_list) >= 2:
                start_of_day = eq_list[0] or start_eq
                latest       = eq_list[-1] or port_val
                realized_today = round(latest - start_of_day, 2)

        snap["pnl"] = {
            "total_unrealized_pl": round(total_unrealized, 2),
            "realized_today":      realized_today,
            "total_return_pct":    round((port_val - start_eq) / start_eq * 100, 4) if start_eq else "N/A",
            "positions_count":     len(snap["positions"]),
            "fills_today":         len(snap["orders"]["filled_today"]),
        }
    except Exception as e:
        snap["errors"].append(f"pnl: {e}")
        snap["pnl"] = {"total_unrealized_pl": "N/A", "realized_today": "N/A"}

    return snap


def write_snapshot(snap):
    os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
    with open(SNAPSHOT_PATH, 'w') as f:
        json.dump(snap, f, indent=2)


def write_pnl_md(snap):
    acct = snap.get("account", {})
    pnl  = snap.get("pnl", {})
    pos  = snap.get("positions", [])
    now  = snap.get("as_of", "?")[:19]

    lines = [
        f"# Paper Trading PnL — {date.today().isoformat()}",
        f"",
        f"**Last updated**: {now} UTC  ",
        f"**Broker**: Alpaca Paper  ",
        f"",
        f"## Account Summary",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Portfolio Value | ${acct.get('portfolio_value', 'N/A'):,.2f} |" if isinstance(acct.get('portfolio_value'), float) else f"| Portfolio Value | N/A |",
        f"| Cash | ${acct.get('cash', 'N/A'):,.2f} |" if isinstance(acct.get('cash'), float) else "| Cash | N/A |",
        f"| Unrealized P&L | ${pnl.get('total_unrealized_pl', 'N/A'):+,.2f} |" if isinstance(pnl.get('total_unrealized_pl'), float) else "| Unrealized P&L | N/A |",
        f"| Realized Today | ${pnl.get('realized_today', 'N/A'):+,.2f} |" if isinstance(pnl.get('realized_today'), float) else f"| Realized Today | {pnl.get('realized_today','N/A')} |",
        f"| Total Return | {pnl.get('total_return_pct', 'N/A'):+.4f}% |" if isinstance(pnl.get('total_return_pct'), float) else f"| Total Return | {pnl.get('total_return_pct','N/A')} |",
        f"| Open Positions | {pnl.get('positions_count', 0)} |",
        f"| Fills Today | {pnl.get('fills_today', 0)} |",
        f"",
    ]

    if pos:
        lines += [
            f"## Positions",
            f"",
            f"| Symbol | Qty | Side | Entry | Current | Unr. P&L | Unr. % |",
            f"|--------|-----|------|-------|---------|----------|--------|",
        ]
        for p in sorted(pos, key=lambda x: abs(x.get('unrealized_pl', 0)), reverse=True):
            lines.append(
                f"| {p['symbol']} | {p['qty']:.4f} | {p['side']} "
                f"| ${p['avg_entry_price']:.2f} | ${p['current_price']:.2f} "
                f"| ${p['unrealized_pl']:+.2f} | {p['unrealized_plpc']*100:+.2f}% |"
            )
        lines.append("")

    if snap["orders"]["filled_today"]:
        lines += [f"## Fills Today", f"", f"| Symbol | Side | Qty | Avg Price | Time |", f"|--------|------|-----|-----------|------|"]
        for o in snap["orders"]["filled_today"]:
            lines.append(f"| {o['symbol']} | {o['side']} | {o['filled_qty']:.4f} | ${o['filled_avg_price']:.2f} | {o['filled_at'][:16]} |")
        lines.append("")

    if snap["errors"]:
        lines += [f"## Errors", ""]
        for e in snap["errors"]: lines.append(f"- {e}")
        lines.append("")

    with open(PNL_PATH, 'w') as f:
        f.write('\n'.join(lines))


def update_history(snap):
    """Append today's summary to rolling history."""
    history = []
    if os.path.exists(HISTORY_PATH):
        try: history = json.load(open(HISTORY_PATH))
        except: pass
    today = date.today().isoformat()
    # Replace or append today's entry
    history = [h for h in history if h.get("date") != today]
    history.append({
        "date":            today,
        "as_of":           snap["as_of"],
        "portfolio_value": snap["account"].get("portfolio_value", "N/A"),
        "unrealized_pl":   snap["pnl"].get("total_unrealized_pl", "N/A"),
        "realized_today":  snap["pnl"].get("realized_today", "N/A"),
        "positions_count": snap["pnl"].get("positions_count", 0),
    })
    history = history[-30:]  # keep 30 days
    with open(HISTORY_PATH, 'w') as f:
        json.dump(history, f, indent=2)


def run():
    snap = build_snapshot()
    write_snapshot(snap)
    write_pnl_md(snap)
    update_history(snap)
    return snap


if __name__ == '__main__':
    snap = run()
    print(f"as_of:           {snap['as_of'][:19]} UTC")
    print(f"portfolio_value: ${snap['account'].get('portfolio_value',0):,.2f}")
    print(f"cash:            ${snap['account'].get('cash',0):,.2f}")
    print(f"unrealized_pl:   ${snap['pnl'].get('total_unrealized_pl','N/A')}")
    print(f"realized_today:  {snap['pnl'].get('realized_today','N/A')}")
    print(f"positions:       {snap['pnl'].get('positions_count',0)}")
    print(f"fills_today:     {snap['pnl'].get('fills_today',0)}")
    if snap["errors"]:
        print(f"errors:          {snap['errors']}")
