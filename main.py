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
        return False
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
            return True
    except Exception as e:
        print(f"[-] Telegram dispatch error: {e}")
        return False

LOCK_MEMBER_THRESHOLD = int(os.environ.get("LOCK_MEMBER_THRESHOLD", "100"))
approval_gate_active = False

def check_member_guard():
    global approval_gate_active
    if approval_gate_active or not BOT_TOKEN or not CHANNEL_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMemberCount?chat_id={CHANNEL_ID}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            count = data.get("result", 0)
            if count >= LOCK_MEMBER_THRESHOLD:
                print(f"[!] 🚨 FOUNDING THRESHOLD REACHED ({count}/{LOCK_MEMBER_THRESHOLD})! ACTIVATING ADMIN PERMISSION GATE...")
                # Create join request invite link requiring admin approval
                gate_url = f"https://api.telegram.org/bot{BOT_TOKEN}/createChatInviteLink"
                payload = json.dumps({
                    "chat_id": CHANNEL_ID,
                    "name": "VIP Approval Gate (Post-100)",
                    "creates_join_request": True
                }).encode('utf-8')
                req2 = urllib.request.Request(gate_url, data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req2, timeout=8) as r2:
                    res2 = json.loads(r2.read().decode())
                    new_link = res2.get("result", {}).get("invite_link", "")
                    print(f"[+] Active Admin Approval Link: {new_link}")
                
                # Broadcast and pin milestone lockdown notice
                lock_text = (
                    "🔒 <b>FIRST 100 FOUNDING SPOTS FILLED!</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "🎉 All 100 free founding passes have been officially claimed!\n\n"
                    "⚠️ <b>Access Policy Update:</b>\n"
                    "Free instant entry is now closed. Member #101 and all future participants require <b>Direct Admin Approval</b> to join.\n\n"
                    "👑 <i>Existing 100 founding members have permanent lifetime access.</i>"
                )
                send_telegram_message(lock_text)
                approval_gate_active = True
    except Exception as e:
        print(f"[-] Member guard check error: {e}")

def tracker_loop():
    print("================================================================")
    print("   SOLANA WHALE RADAR CLOUD DAEMON ACTIVE (24/7)")
    print("================================================================")
    print(f"  • Monitored Pools: {len(MONITORED_POOLS)}")
    print(f"  • Min Whale Size:  ${MIN_WHALE_USD:,.0f} USD")
    print(f"  • Member Cap Gate: {LOCK_MEMBER_THRESHOLD} Members")
    print(f"  • Channel:         {CHANNEL_ID}")
    print("================================================================\n")
    
    # Warm-up pass: pre-populate cache with current pool transactions so restarts never trigger a historical burst
    print("[*] Performing startup cache warm-up (shielding from restart bursts)...")
    for pool in MONITORED_POOLS:
        try:
            initial_trades = fetch_real_pool_trades(pool["address"])
            for t in initial_trades:
                tx = t.get("attributes", {}).get("tx_hash")
                if tx:
                    mark_tx_seen(tx)
        except Exception as e:
            print(f"[-] Warmup notice ({pool['symbol']}): {e}")
        time.sleep(1)
    print(f"[+] Warm-up complete! Pre-cached {len(seen_cache)} existing transactions. Live monitoring active.\n")
    
    last_guard_check = 0
    while True:
        try:
            now = time.time()
            if now - last_guard_check > 300: # Check member count every 5 minutes
                last_guard_check = now
                check_member_guard()
                
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
    t = threading.Thread(target=start_healthcheck_server, daemon=True)
    t.start()
    tracker_loop()
