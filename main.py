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
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.stdout.reconfigure(encoding='utf-8')
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")
MIN_WHALE_USD = float(os.environ.get("MIN_WHALE_USD", "5000.0"))
PORT = int(os.environ.get("PORT", "8000"))

seen_cache = set()

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
    kind = (trade_attrs.get("kind") or "buy").upper()
    volume_usd = float(trade_attrs.get("volume_in_usd") or 0.0)
    price_usd = float(trade_attrs.get("price_to_in_usd") or trade_attrs.get("price_from_in_usd") or 0.0)
    block_timestamp = trade_attrs.get("block_timestamp", "")
    
    if volume_usd >= 25000:
        badge = "🚨 <b>MEGA WHALE BUY</b> 🐋🐋"
    elif volume_usd >= 10000:
        badge = "🟢 <b>BIG WHALE BUY</b> 🐋"
    else:
        badge = "🟢 <b>WHALE BUY</b> 🐋"
    
    msg = (
        f"{badge}\n\n"
        f"💰 <b>Amount:</b> ${volume_usd:,.2f} USD\n"
        f"🪙 <b>Token:</b> {pool_info['name']} (<b>${pool_info['symbol']}</b>)\n"
        f"💵 <b>Execution Price:</b> ${price_usd:.6f}\n"
        f"👤 <b>Wallet:</b> <code>{wallet[:6]}...{wallet[-6:] if len(wallet) > 12 else wallet}</code>\n"
        f"⏰ <b>On-Chain Time:</b> {block_timestamp}\n\n"
        f"🔍 <b>Contract:</b> <code>{pool_info['token']}</code>\n"
        f"📈 <b>Live Chart:</b> <a href=\"https://dexscreener.com/solana/{pool_info['address']}\">DexScreener</a>\n"
        f"🔗 <b>Solscan Tx Proof:</b> <a href=\"https://solscan.io/tx/{tx_hash}\">Verify on Solscan</a>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔥 <i>100% Verified Real On-Chain Swap | Data only, not financial advice.</i>"
    )
    return msg

def send_telegram_message(html_text):
    if not BOT_TOKEN or not CHANNEL_ID:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": CHANNEL_ID,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True
    except Exception as e:
        print(f"[-] Telegram dispatch error: {e}")
        return False

def tracker_loop():
    print("================================================================")
    print("   SOLANA WHALE RADAR CLOUD DAEMON ACTIVE (24/7)")
    print("================================================================")
    print(f"  • Monitored Pools: {len(MONITORED_POOLS)}")
    print(f"  • Min Whale Size:  ${MIN_WHALE_USD:,.0f} USD")
    print(f"  • Channel:         {CHANNEL_ID}")
    print("================================================================\n")
    
    while True:
        try:
            for pool in MONITORED_POOLS:
                trades = fetch_real_pool_trades(pool["address"])
                for t in trades:
                    attrs = t.get("attributes", {})
                    tx_hash = attrs.get("tx_hash")
                    volume_usd = float(attrs.get("volume_in_usd") or 0.0)
                    kind = (attrs.get("kind") or "").upper()
                    
                    if not tx_hash or tx_hash in seen_cache:
                        continue
                        
                    seen_cache.add(tx_hash)
                    if len(seen_cache) > 5000:
                        seen_cache.clear()
                        
                    if volume_usd >= MIN_WHALE_USD and kind == "BUY":
                        alert_msg = format_real_trade_alert(pool, attrs)
                        send_telegram_message(alert_msg)
                        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 🚨 BROADCAST: ${volume_usd:,.2f} on {pool['symbol']} | Tx: {tx_hash[:12]}...")
                        time.sleep(2)
                        
                time.sleep(3)
            time.sleep(20)
        except Exception as e:
            print(f"[-] Tracker loop error: {e}")
            time.sleep(20)

if __name__ == "__main__":
    t = threading.Thread(target=start_healthcheck_server, daemon=True)
    t.start()
    tracker_loop()
