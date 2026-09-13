"""
Solana Whale Radar - 24/7 Cloud Engine (Koyeb & Docker Ready)
Monitors real-time on-chain trades across Solana DEX pools and streams alerts to Telegram.
Includes an embedded HTTP healthcheck endpoint for 24/7 cloud hosting platforms.
"""

import urllib.request
import json
import time
import datetime
import sys
import os
import threading
import collections
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.stdout.reconfigure(encoding='utf-8')
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")
MIN_WHALE_USD = float(os.environ.get("MIN_WHALE_USD", "5000.0"))
PORT = int(os.environ.get("PORT", "8000"))
WELCOME_AUTO_DELETE_SECONDS = int(os.environ.get("WELCOME_AUTO_DELETE_SECONDS", "90"))

# Dual-layer sliding window deduplication cache
seen_cache = set()
seen_queue = collections.deque()

def mark_tx_seen(tx_hash):
    """Adds tx_hash to cache with continuous FIFO sliding window (never wipes to zero)."""
    if not tx_hash or tx_hash in seen_cache:
        return False
    seen_cache.add(tx_hash)
    seen_queue.append(tx_hash)
    if len(seen_queue) > 4000:
        oldest = seen_queue.popleft()
        seen_cache.discard(oldest)
    return True

MONITORED_POOLS = [
    {"symbol": "RAY", "name": "Raydium", "address": "2AXXcN6oN9bBT5owwmTH53C7QHUXvhLeu718Kqt8rvY2", "token": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"},
    {"symbol": "SOL", "name": "Solana (USDC)", "address": "Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE", "token": "So11111111111111111111111111111111111111112"},
    {"symbol": "JUP", "name": "Jupiter", "address": "22Mm2UHAh2pdP3PFj9wf2i43e2r2Z2B8z3c5J4mFmP3U", "token": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"},
    {"symbol": "BONK", "name": "Bonk", "address": "8PhnCfgqpgFM7ZJvttGdBVMYps84Mt3kVhFMQFoxx99m", "token": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"},
    {"symbol": "WIF", "name": "dogwifhat", "address": "EP2ib6dYdEeqD8MfE2ezHCxX3kEDNgC9JxWqjNR8ZEmk", "token": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"}
]

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        status = {
            "status": "healthy",
            "service": "solana-whale-radar",
            "min_whale_usd": MIN_WHALE_USD,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "cached_tx": len(seen_cache)
        }
        self.wfile.write(json.dumps(status).encode("utf-8"))
        
    def log_message(self, format, *args):
        pass # Silence web access logs

def start_healthcheck_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthCheckHandler)
    print(f"[+] Embedded health check server active on port {PORT}")
    server.serve_forever()

def fetch_real_pool_trades(pool_address):
    url = f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool_address}/trades"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get("data", [])
    except Exception:
        return []

def format_real_trade_alert(pool_info, trade_attrs):
    tx_hash = trade_attrs.get("tx_hash", "")
    wallet = trade_attrs.get("tx_from_address", "")
    volume_usd = float(trade_attrs.get("volume_in_usd") or 0.0)
    price_usd = float(trade_attrs.get("price_to_in_usd") or trade_attrs.get("price_from_in_usd") or 0.0)
    block_timestamp = trade_attrs.get("block_timestamp", "")
    
    # Calculate SOL amount if available
    from_token_addr = trade_attrs.get("from_token_address", "")
    to_token_addr = trade_attrs.get("to_token_address", "")
    sol_mint = "So11111111111111111111111111111111111111112"
    
    sol_amount = 0.0
    if from_token_addr == sol_mint:
        sol_amount = float(trade_attrs.get("from_token_amount") or 0.0)
    elif to_token_addr == sol_mint:
        sol_amount = float(trade_attrs.get("to_token_amount") or 0.0)
    
    # Clean time format
    time_display = block_timestamp
    if "T" in block_timestamp:
        time_display = block_timestamp.split("T")[1].replace("Z", "")[:8] + " UTC"
    
    # Dynamic visual volume bars & badge
    if volume_usd >= 50000:
        bars = "🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢"
        badge = "🚨 <b>TITAN WHALE BUY DETECTED!</b> 🐋🐋🐋"
    elif volume_usd >= 25000:
        bars = "🟢🟢🟢🟢🟢🟢🟢"
        badge = "🚨 <b>MEGA WHALE BUY DETECTED!</b> 🐋🐋"
    elif volume_usd >= 10000:
        bars = "🟢🟢🟢🟢🟢"
        badge = "🟢 <b>BIG WHALE BUY DETECTED!</b> 🐋"
    else:
        bars = "🟢🟢🟢"
        badge = "🟢 <b>WHALE BUY DETECTED!</b> 🐋"
    
    token_addr = pool_info['token']
    pool_addr = pool_info['address']
    symbol = pool_info['symbol'].upper()
    name = pool_info['name']
    
    # Dynamic price formatting
    if price_usd >= 1.0:
        price_str = f"${price_usd:,.2f}"
    elif price_usd >= 0.001:
        price_str = f"${price_usd:.5f}"
    else:
        price_str = f"${price_usd:.8f}"
        
    wallet_short = f"{wallet[:6]}...{wallet[-6:]}" if len(wallet) > 12 else wallet
    spent_str = f"<b>{sol_amount:,.1f} SOL</b> (${volume_usd:,.2f} USD)" if sol_amount > 0 else f"<b>${volume_usd:,.2f} USD</b>"
    
    msg = (
        f"{bars}\n"
        f"{badge}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💎 <b>Token:</b> {name} (<b>${symbol}</b>)\n"
        f"💰 <b>Spent:</b> {spent_str}\n"
        f"🎯 <b>Price:</b> <code>{price_str}</code>\n"
        f"👤 <b>Whale:</b> <code>{wallet_short}</code>\n"
        f"⏰ <b>Time:</b> <code>{time_display}</code>\n"
        f"🧾 <b>Receipt:</b> <a href=\"https://solscan.io/tx/{tx_hash}\">Verified Solscan Proof ↗</a>\n\n"
        f"📜 <b>Mint Address:</b> <i>(tap to copy)</i>\n"
        f"<code>{token_addr}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📡 <i>Solana Whale Radar • Verified On-Chain Alpha</i>"
    )
    
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🛡️ RugCheck", "url": f"https://rugcheck.xyz/tokens/{token_addr}"},
                {"text": "📈 DexScreener", "url": f"https://dexscreener.com/solana/{pool_addr}"}
            ],
            [
                {"text": "⚡ Trojan Bot", "url": f"https://t.me/solana_trojanbot?start={token_addr}"},
                {"text": "🚀 Photon DEX", "url": f"https://photon-sol.tinyastro.io/en/lp/{token_addr}"}
            ]
        ]
    }
    
    return msg, keyboard

def send_telegram_message(html_text, reply_markup=None):
    if not BOT_TOKEN or not CHANNEL_ID:
        return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload_dict = {
        "chat_id": CHANNEL_ID,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload_dict["reply_markup"] = reply_markup
    payload = json.dumps(payload_dict).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get("result", {}).get("message_id")
    except Exception as e:
        print(f"[-] Telegram dispatch error: {e}")
        return None

def delete_telegram_message(message_id, delay=0):
    if not BOT_TOKEN or not CHANNEL_ID or not message_id:
        return
    if delay > 0:
        time.sleep(delay)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
    payload = json.dumps({"chat_id": CHANNEL_ID, "message_id": message_id}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass

def welcome_listener_daemon():
    """Background listener for new members joining the public supergroup."""
    if not BOT_TOKEN or not CHANNEL_ID:
        return
        
    print("[*] Initializing Telegram Welcome Listener...")
    offset = 0
    try:
        sync_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset=-1"
        req = urllib.request.Request(sync_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8')).get("result", [])
            if data:
                offset = data[-1]["update_id"] + 1
    except Exception as e:
        print(f"[-] Welcome listener offset sync notice: {e}")
        
    print(f"[+] Welcome Listener active (offset: {offset}) - Monitoring new members.")
    
    while True:
        try:
            poll_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=20&allowed_updates=[\"message\"]"
            req = urllib.request.Request(poll_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                updates = json.loads(resp.read().decode('utf-8')).get("result", [])
                
            for u in updates:
                offset = max(offset, u["update_id"] + 1)
                msg = u.get("message")
                if not msg:
                    continue
                chat = msg.get("chat", {})
                if str(chat.get("id")) != str(CHANNEL_ID):
                    continue
                    
                new_members = msg.get("new_chat_members", [])
                if new_members:
                    # Clean up raw Telegram service message ("X joined the group")
                    service_msg_id = msg.get("message_id")
                    if service_msg_id:
                        threading.Thread(target=delete_telegram_message, args=(service_msg_id, 1), daemon=True).start()
                        
                    for member in new_members:
                        if member.get("is_bot"):
                            continue
                        name = member.get("first_name") or "Trader"
                        welcome_card = (
                            f"👋 <b>Welcome {name} to Solana Whale Radar!</b> 🐋\n\n"
                            f"You're in a <b>100% Free 24/7 On-Chain Alpha Terminal</b> streaming verified Solana DEX swaps >$5,000 USD in real time.\n\n"
                            f"⚡ <b>What you get here:</b>\n"
                            f"• Real-time alerts on large Raydium/Orca swaps\n"
                            f"• 🛡️ 1-Click RugCheck safety verification\n"
                            f"• 🧾 Solscan cryptographic transaction receipts\n\n"
                            f"📌 <i>Tap below to read our 1-minute welcome guide on spotting whale accumulation!</i>\n"
                            f"🔔 <i>Turn notifications ON to catch moves early!</i>"
                        )
                        keyboard = {
                            "inline_keyboard": [
                                [{"text": "📌 Read Welcome Guide", "url": "https://t.me/solanawhaleradar/619"}]
                            ]
                        }
                        sent_msg_id = send_telegram_message(welcome_card, reply_markup=keyboard)
                        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🤝 WELCOMED: {name} (Msg ID: {sent_msg_id})")
                        if sent_msg_id and WELCOME_AUTO_DELETE_SECONDS > 0:
                            threading.Thread(target=delete_telegram_message, args=(sent_msg_id, WELCOME_AUTO_DELETE_SECONDS), daemon=True).start()
                            
        except (TimeoutError, urllib.error.URLError):
            time.sleep(1)
        except Exception as e:
            print(f"[-] Welcome listener loop notice: {e}")
            time.sleep(5)

LEDGER_FILE = "whale_ledger.json"
daily_trades = []

def load_whale_ledger():
    global daily_trades
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                daily_trades = json.load(f)
            cutoff = time.time() - 86400
            daily_trades = [t for t in daily_trades if t.get("timestamp", 0) >= cutoff]
            print(f"[+] Loaded {len(daily_trades)} trades from 24h whale ledger.")
        except Exception as e:
            print(f"[-] Ledger load notice: {e}")
            daily_trades = []

def record_whale_trade(pool, attrs, volume_usd):
    trade_item = {
        "timestamp": time.time(),
        "symbol": pool["symbol"],
        "name": pool["name"],
        "volume_usd": volume_usd,
        "kind": (attrs.get("kind") or "").upper(),
        "tx_hash": attrs.get("tx_hash") or "",
        "block_timestamp": attrs.get("block_timestamp") or ""
    }
    daily_trades.append(trade_item)
    cutoff = time.time() - 86400
    while daily_trades and daily_trades[0]["timestamp"] < cutoff:
        daily_trades.pop(0)
    try:
        with open(LEDGER_FILE, "w", encoding="utf-8") as f:
            json.dump(daily_trades, f)
    except Exception:
        pass

def build_daily_recap_card():
    if not daily_trades:
        return None, None
    cutoff = time.time() - 86400
    valid_trades = [t for t in daily_trades if t.get("timestamp", 0) >= cutoff]
    if not valid_trades:
        return None, None
        
    total_vol = sum(t["volume_usd"] for t in valid_trades)
    trade_count = len(valid_trades)
    largest = max(valid_trades, key=lambda x: x["volume_usd"])
    
    pool_vols = collections.defaultdict(float)
    for t in valid_trades:
        pool_vols[t["symbol"]] += t["volume_usd"]
        
    top_symbol = max(pool_vols.items(), key=lambda x: x[1])[0]
    
    breakdown_lines = []
    for sym, vol in sorted(pool_vols.items(), key=lambda x: x[1], reverse=True):
        pct = (vol / total_vol) * 100 if total_vol > 0 else 0
        breakdown_lines.append(f"• <b>${sym}:</b> ${vol:,.0f} ({pct:.1f}%)")
    breakdown_text = "\n".join(breakdown_lines)
    
    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    
    recap_html = (
        f"👑 <b>SOLANA WHALE RADAR | 24H DAILY RECAP</b> 📊\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>Snapshot:</b> {now_utc}\n\n"
        f"💰 <b>Total Whale Inflow:</b> ${total_vol:,.2f} USD\n"
        f"⚡ <b>Large Swaps Detected:</b> {trade_count} trades (>${MIN_WHALE_USD:,.0f})\n"
        f"🏆 <b>Top Inflow Token:</b> ${top_symbol} (${pool_vols[top_symbol]:,.2f})\n\n"
        f"👑 <b>Largest Single Swap:</b>\n"
        f"• Asset: <b>${largest['symbol']} ({largest['name']})</b>\n"
        f"• Volume: <b>${largest['volume_usd']:,.2f} USD</b>\n"
        f"• Solscan Proof: <a href=\"https://solscan.io/tx/{largest['tx_hash']}\">Receipt 🧾</a>\n\n"
        f"📈 <b>Volume Distribution:</b>\n"
        f"{breakdown_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <a href=\"https://t.me/solanawhaleradar/619\">Read Pinned Welcome Guide</a>\n"
        f"🔔 <i>Turn notifications ON to catch moves in real time!</i>"
    )
    
    keyboard = {
        "inline_keyboard": [
            [{"text": "📌 Welcome Guide", "url": "https://t.me/solanawhaleradar/619"}],
            [{"text": "🛡️ Live RugCheck Audit", "url": "https://rugcheck.xyz"}]
        ]
    }
    return recap_html, keyboard

def daily_recap_scheduler():
    """Dispatches a 24-hour consolidated whale recap every day at 00:00 UTC."""
    last_recap_date = None
    print("[*] Daily Whale Recap Scheduler active (target: 00:00 UTC).")
    while True:
        try:
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            current_date = now_utc.date()
            if now_utc.hour == 0 and now_utc.minute >= 0 and last_recap_date != current_date:
                card_html, keyboard = build_daily_recap_card()
                if card_html:
                    send_telegram_message(card_html, reply_markup=keyboard)
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 👑 Dispatched Daily Whale Recap to Telegram!")
                last_recap_date = current_date
        except Exception as e:
            print(f"[-] Daily recap scheduler notice: {e}")
        time.sleep(30)

def tracker_loop():
    print("================================================================")
    print("   SOLANA WHALE RADAR CLOUD DAEMON ACTIVE (24/7)")
    print("================================================================")
    print(f"  • Monitored Pools: {len(MONITORED_POOLS)}")
    print(f"  • Min Whale Size:  ${MIN_WHALE_USD:,.0f} USD")
    print(f"  • Access Policy:   100% Free Public Channel")
    print(f"  • Channel:         {CHANNEL_ID}")
    print("================================================================\n")
    
    # Warm-up pass: pre-populate cache with current pool transactions so restarts never trigger a historical burst
    print("[*] Performing startup cache warm-up (shielding from restart bursts)...")
    for pool in MONITORED_POOLS:
        try:
            initial_trades = fetch_real_pool_trades(pool["address"])
            for t in initial_trades:
                attrs = t.get("attributes", {})
                tx = attrs.get("tx_hash")
                vol = float(attrs.get("volume_in_usd") or 0.0)
                k = (attrs.get("kind") or "").upper()
                if tx:
                    mark_tx_seen(tx)
                if vol >= MIN_WHALE_USD and k == "BUY":
                    record_whale_trade(pool, attrs, vol)
        except Exception as e:
            print(f"[-] Warmup notice ({pool['symbol']}): {e}")
        time.sleep(1)
    print(f"[+] Warm-up complete! Pre-cached {len(seen_cache)} existing transactions ({len(daily_trades)} in 24h ledger). Live monitoring active.\n")
    
    while True:
        try:
                
            for pool in MONITORED_POOLS:
                trades = fetch_real_pool_trades(pool["address"])
                for t in trades:
                    attrs = t.get("attributes", {})
                    tx_hash = attrs.get("tx_hash")
                    volume_usd = float(attrs.get("volume_in_usd") or 0.0)
                    kind = (attrs.get("kind") or "").upper()
                    block_timestamp = attrs.get("block_timestamp", "")
                    
                    if not tx_hash or tx_hash in seen_cache:
                        continue
                        
                    # Strict Age Guard: ignore trades older than 6 minutes (prevents historical replay)
                    if block_timestamp:
                        try:
                            trade_dt = datetime.datetime.fromisoformat(block_timestamp.replace("Z", "+00:00"))
                            age_sec = (datetime.datetime.now(datetime.timezone.utc) - trade_dt).total_seconds()
                            if age_sec > 360: # 6 minutes old
                                mark_tx_seen(tx_hash)
                                continue
                        except Exception:
                            pass
                            
                    mark_tx_seen(tx_hash)
                        
                    if volume_usd >= MIN_WHALE_USD and kind == "BUY":
                        record_whale_trade(pool, attrs, volume_usd)
                        alert_msg, keyboard = format_real_trade_alert(pool, attrs)
                        send_telegram_message(alert_msg, reply_markup=keyboard)
                        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🚨 BROADCAST: ${volume_usd:,.2f} on {pool['symbol']} | Tx: {tx_hash[:12]}...")
                        time.sleep(2)
                        
                time.sleep(2)
            time.sleep(10)
        except Exception as e:
            print(f"[-] Tracker loop error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    load_whale_ledger()
    t_health = threading.Thread(target=start_healthcheck_server, daemon=True)
    t_health.start()
    t_welcome = threading.Thread(target=welcome_listener_daemon, daemon=True)
    t_welcome.start()
    t_recap = threading.Thread(target=daily_recap_scheduler, daemon=True)
    t_recap.start()
    tracker_loop()
