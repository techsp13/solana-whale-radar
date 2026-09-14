# 🐋 Solana Whale & Smart-Money Radar (Autonomous On-Chain Daemon)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Network: Solana](https://img.shields.io/badge/Network-Solana%20Mainnet-14F195?logo=solana)](https://solana.com/)
[![Telegram: Live Radar](https://img.shields.io/badge/Telegram-Live%20Whale%20Radar-2CA5E0?logo=telegram)](https://t.me/+8dLwdoXGoCY5M2Fl)
[![Status: 24/7 Active](https://img.shields.io/badge/Status-Live%20Streaming-brightgreen.svg)]()

An autonomous, zero-latency on-chain monitoring daemon for the Solana ecosystem. It tracks high-volume liquidity pool swaps across Raydium, Orca, and Meteora, filtering out noise and streaming real-time whale transactions ($5,000+ USD) with RugCheck audits and Solscan receipts.

---

## 📡 Live Stream Demo

Want to see the bot in action without self-hosting?
Join the 24/7 live alert terminal on Telegram:

👉 **[Join Solana Whale Radar (100% Free Live Feed)](https://t.me/+8dLwdoXGoCY5M2Fl)**

---

## ⚡ Key Features

- **Filtered Signal (Zero Noise):** Filters out retail micro-swaps. Only triggers for verified whale buys exceeding **$5,000+ USD** (with tiered badges for $10k+ and $25k+ Mega Whales).
- **100% On-Chain Proof:** Every alert includes the direct **Solscan Transaction Receipt**, proving zero simulated or fake volume.
- **Safety Heuristics:** Instant 1-click **RugCheck** link embedded in every alert to inspect mint authority, freeze authority, and top holder concentration before entering.
- **1-Tap Fast Execution:** Instant deep-links to **Trojan on Solana** and **Photon** for split-second manual or automated trade execution.
- **24/7 Headless Deployment:** Designed to run continuously on lightweight cloud containers (Docker / Render / VPS) with automated keep-alive health checks.

---

## 🛠️ Tech Stack & Architecture

- **Language:** Python 3.11+ (asyncio, aiohttp)
- **Data Pipeline:** Raydium AMM / CLMM liquidity pool streaming via DexScreener & RPC endpoints
- **Delivery Engine:** Telegram Bot API (MarkdownV2 with interactive quick-action buttons)
- **Hosting:** Docker containerized, HTTP keep-alive daemon on port 8000

```
┌─────────────────────────┐
│ Solana DEX Swaps        │
│ (Raydium, Orca, Meteora)│
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Filter & Validation     │ ──> Ignores < $5,000 retail noise
│ (Async Python Daemon)   │ ──> Solscan receipt validation
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Broadcast Layer         │ ──> Solscan Tx Proof
│ (Telegram Bot API)      │ ──> RugCheck Score
└─────────────────────────┘     └──> 1-Tap Trojan & Photon Links
```

---

## 🚀 Quickstart (Self-Hosting)

### 1. Clone the repository
```bash
git clone https://github.com/techsp13/solana-whale-radar.git
cd solana-whale-radar
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create an `.env` file or export your keys:
```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHANNEL_ID="your_channel_or_chat_id"
export PORT="8000"
```

### 4. Run the Daemon
```bash
python main.py
```

---

## 📄 License
Released under the [MIT License](LICENSE).
