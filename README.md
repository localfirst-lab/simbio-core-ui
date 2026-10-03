# Simbio Core & Web UI: Sovereign Pocket AI Laboratory

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20LLM-black.svg?logo=ollama&logoColor=white)](https://ollama.com/)
[![PWA](https://img.shields.io/badge/PWA-Mobile%20Ready-purple.svg?logo=pwa&logoColor=white)](https://web.dev/progressive-web-apps/)
[![License](https://img.shields.io/badge/License-Non--Commercial%20Research-orange.svg)](#license)
[![Organization](https://img.shields.io/badge/Org-localfirst--lab-emerald.svg)](https://github.com/localfirst-lab)

> **A production-grade, local-first neural gateway that turns any Linux VPS and smartphone into a sovereign, private AI laboratory in your pocket.**

---

## 🌍 Executive Summary (IT / DE / EN)

- **EN**: *Simbio Core & UI* empowers developers and researchers to run open-weight models (Qwen, Gemma, Mistral) on their private VPS infrastructure while monitoring hardware telemetry, streaming journalctl logs, and chatting with multimodal AI directly from a mobile browser.
- **IT**: *Simbio Core & UI* trasforma la tua VPS in un laboratorio di intelligenza artificiale tascabile gestibile interamente da smartphone: chat neurale multimodale, telemetria hardware istantanea, terminale log con filtri in tempo reale e salvataggio su canale Telegram sovrano.
- **DE**: *Simbio Core & UI* verwandelt Ihren VPS in ein souveränes Taschen-KI-Labor, das vollständig über das Smartphone gesteuert werden kann: multimodaler Chat, Hardware-Telemetrie in Echtzeit, Terminal-Logs mit Filtern und Notarisierung auf einem privaten Telegram-Kanal.

---

## 🏛️ Tri-Tier Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        1. SMARTPHONE PWA (CLIENT)                      │
│  - Multimodal Neural Chat (Markdown / KaTeX / Vision)                  │
│  - Instant Model Switcher (Lite 2B vs Core 14B)                        │
│  - Live Hardware Mini-Ticker (RAM / CPU / Linux Uptime)                │
│  - Real-time Journalctl Terminal (Filter: ALLE, FEHLER, API, OLLAMA)   │
│  - Native Bilingual UI Engine (Italian & German)                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Encrypted HTTPS / WSS
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       2. VPS KERNEL & GATEWAY                          │
│  - FastAPI Asynchronous Core & Streaming Server-Sent Events (SSE)      │
│  - Load-Bearing Zero-Trust Anchor (core_integrity.py)                  │
│  - SQLite Multi-Session Storage (WAL Mode, Foreign Key Cascades)       │
│  - Local Ollama Orchestration Daemon (127.0.0.1:11434)                 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Safe Webhook / API
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   3. TELEGRAM EXTERNAL CLOUD NOTARY                    │
│  - Independent ledger & decentralized off-site journal                 │
│  - Zero cloud vendor lock-in (No Big Tech storage dependencies)        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Core Capabilities & Features

### 1. 📱 Sovereign Pocket Laboratory (Mobile PWA)
- **Installable Web App**: Add directly to your iOS or Android home screen with native full-screen app experience.
- **Low Latency & Adaptive UI**: Built with modern Tailwind CSS glassmorphism, responsive gestures (swipe-down terminal dismissal), and tactile haptic feedback.
- **Bilingual Interface**: Native support for **Italian** (`IT`) and **German** (`DE`) with instant persistent toggle (`localStorage`).

### 2. 💬 Multimodal Streaming Chat & Neural Switching
- **SSE Streamlined Inference**: Real-time token streaming with live thinking heartbeat (EKG status pulse).
- **Dynamic Dual-Model Mode**:
  - `⚡ Lite`: Sub-second latency for quick queries and conversational routing (e.g. 2B models).
  - `🧠 Core`: High-parameter deep reasoning, strategic planning, and code generation (e.g. 14B+ models).
- **Vision & File Ingestion**: Upload diagrams, screenshots, and delivery notes directly from the smartphone camera or gallery for vision-language analysis.

### 3. 📊 Live Hardware Telemetry
- Inspect server health at a glance without opening an SSH terminal.
- Real-time monitoring of:
  - **RAM Memory**: Allocated GB, Total Capacity, and Percentage load.
  - **CPU Core Utilization**: Dynamic multi-core stress metrics.
  - **Uptime**: True Linux kernel uptime calculation.

### 4. 📟 Terminal Log Streamer with Instant Filters
- Direct live streaming of `journalctl` system logs and Ollama inferencing events over HTTP.
- Instant categorisation:
  - `[ALLE / TUTTI]`: Full unified service feed.
  - `[API]`: Uvicorn HTTP endpoints and gateway latency.
  - `[OLLAMA]`: Neural model loading, KV cache allocation, and token generation speed.
  - `[FEHLER 🔴 / ERRORI 🔴]`: Immediate capture of anomalies and stack traces.
- One-click log export and download to text file.

### 5. 🕸️ Neural Orchestra & JSON Architecture
- Dedicated visual matrix showing specialized model assignments (Planner, Code Engineer, Compliance Auditor, Gatekeeper).
- Model Context Protocol (MCP) and JSON tool-use readiness.

### 6. 🛡️ Autonomous Security Shield & Firewall Agent (Pydantic Protected)
- **24/7 Background Sentinel Daemon** (`scripts/vps_monitor_agent.py`): Continuous monitoring of SSH authentication logs (`/var/log/auth.log`) and active network sockets.
- **Kernel-Level Mitigation**: Automatic, zero-delay execution of Linux `iptables` DROP rules against brute-force intrusion and fictitious user bot-scans.
- **Pydantic Validation**: All IP operations and unban requests are strongly validated through Pydantic schemas, enforcing immutable whitelists to eliminate self-lockouts.
- **Live Visual Dashboard** (`/security`): Real-time attack telemetry, interactive ban/unban controls, and dynamic bicultural localization (IT/DE) of security reasons.

### 7. 💻 Interactive Mobile Bash Console (`/console`)
- **Direct Smartphone CLI**: Execute authenticated shell and diagnostic commands (`htop`, `systemctl status`, `iptables -L`) straight from your mobile PWA.
- **Constant-Time Verification**: High-security token gating prevents timing attacks while executing shell calls securely over HTTPS.

### 8. 📜 Sovereign Telegram Ledger & Bordbuch Notary
- **1-Click Architectural Notarization**: Directly record milestones and security updates from the drawer menu into both persistent local ledger files (`diario_storico.json`/`.txt`) and an off-site Telegram broadcast channel.

### 9. 🔒 Load-Bearing Core Integrity (`core_integrity.py`)
- Employs zero-trust cryptographic root anchoring (`_SYS_ENTROPY_VECTOR`).
- **Load-Bearing Dependency**: Authentication and session layers derive internal cryptographic salts directly from the author's mathematical anchor. If the file is altered or removed, the gateway terminates immediately (`RuntimeError: FATAL: Core integrity compromised`).

---

## 🚀 Quick Start & Deployment

### Prerequisites
- A Linux VPS or dedicated host (Ubuntu 22.04 / 24.04 or Debian recommended).
- Python 3.10 or higher.
- [Ollama](https://ollama.com/) running locally on `http://127.0.0.1:11434`.

### 1. Clone & Configure
```bash
git clone https://github.com/localfirst-lab/simbio-core-ui.git
cd simbio-core-ui

# Copy environment template
cp .env.example .env
```

### 2. Configure Environment Variables (`.env`)
Edit `.env` and configure your secure tokens:
```ini
# Generate with: openssl rand -hex 32
SIMBIO_API_KEY=<YOUR_SECURE_API_KEY_HERE>
HOST=0.0.0.0
PORT=8000

OLLAMA_BASE_URL=http://127.0.0.1:11434
DEFAULT_MODEL=qwen2.5:14b
ALLOWED_ORIGINS=*

# Optional Telegram Sovereign Notary:
TELEGRAM_BOT_TOKEN=<YOUR_TELEGRAM_BOT_TOKEN>
TELEGRAM_CHAT_ID=<YOUR_TELEGRAM_CHAT_ID>
```

### 3. Automated One-Click Systemd Deployment
Run the included deployment script:
```bash
chmod +x deploy_api.sh
sudo ./deploy_api.sh
```
This script automatically:
1. Provisions an isolated Python virtual environment (`venv/`).
2. Installs dependencies (`fastapi`, `uvicorn`, `psutil`, `httpx`, `python-dotenv`).
3. Registers and starts the `simbio-api.service` systemd daemon.
4. Verifies the `/health` endpoint status.

### 4. Verify Gateway Health
```bash
curl -i http://127.0.0.1:8000/health
```
Expected output:
```http
HTTP/1.1 200 OK
content-type: application/json
x-core-engine: localfirst-core/df791c1dd6ae

{"status":"ONLINE","service":"Simbio Core API & UI","version":"2.0.0","engine":"localfirst-core/df791c1dd6ae"}
```

---

## 📱 Mobile Client Setup
1. In your smartphone browser, navigate to: `https://<YOUR_VPS_DOMAIN_OR_IP>/`
2. Open the browser menu and select **"Add to Home Screen"** / **"Zum Startbildschirm hinzufügen"**.
3. Launch the app and input your API token in the settings prompt (saved securely in your local browser sandbox).

---

## 📂 Repository Structure

```
simbio-core-ui/
├── core_integrity.py      # Zero-trust cryptographic anchor & load-bearing author signature
├── auth.py                # Constant-time token verification & timing attack shield
├── config.py              # Dynamic environment loader (.env)
├── config_monitor.example.json # Template for autonomous security agent configuration
├── database.py            # SQLite multi-session chat engine (WAL mode)
├── main.py                # FastAPI ASGI application & static route dispatcher
├── deploy_api.sh          # One-click systemd daemon installer
├── test_api.py            # Local & remote API validation test harness
├── requirements.txt       # Production dependencies
├── .env.example           # Sanitized environment configuration template
├── .gitignore             # Comprehensive secret, state, and database exclusion
├── LICENSE                # Community Non-Commercial Research License
├── routes/
│   ├── chat.py            # SSE streaming completions & Ollama router
│   ├── security.py        # Pydantic IP validator, iptables executor & security stats
│   ├── system.py          # Real-time hardware telemetry & bash command execution
│   ├── sessions.py        # Chat session lifecycle (create, rename, delete)
│   ├── media.py           # Multimodal image upload handler
│   └── telegram.py        # Sovereign Telegram notary & local diary sync
├── scripts/
│   └── vps_monitor_agent.py # 24/7 autonomous security sentinel & firewall drop agent
├── static/
│   ├── manifest.json      # PWA configuration manifest
│   ├── sw.js              # Service Worker for native standalone PWA experience
│   ├── simbio_icon.png    # High-resolution mobile application icon
│   └── uploads/           # Ephemeral media upload directory (.gitkeep)
└── templates/
    ├── index.html         # Main Mobile PWA Chat interface (IT/DE) & Notary Modal
    ├── hardware.html      # Hardware telemetry & sensor monitor
    ├── console.html       # Live log terminal & interactive bash console
    ├── orchestra.html     # Model orchestration & MCP matrix
    └── security.html      # VPS Security Shield & IP ban management dashboard (IT/DE)
```

---

## 📜 License

This project is licensed under the **Community Source & Non-Commercial Research License**.

- ✅ **Free for Personal Use, Educational Testing, and Scientific Research.**
- ✅ **Community Improvements & Forks Welcome** (encouraged to submit back).
- ❌ **Commercial exploitation, resale, or bundling into proprietary client deliverables is strictly prohibited** without prior written authorization from the author.

---

## 👤 Author & Intellectual Attribution

Designed and engineered by **Davide Carrieri**  
Founder, **[Local-First Lab](https://github.com/localfirst-lab)**  
*Empowering individuals with sovereign, local-first artificial intelligence.*
