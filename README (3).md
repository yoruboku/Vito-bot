# 🤖 Vito Bot  
![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Discord API](https://img.shields.io/badge/Discord-API-lightgrey)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

**High-Performance Persistent Discord AI Bot**

Vito is a low-latency, context-aware Discord bot engineered for speed, memory retention, and long-term conversational consistency.  
Built by **Yoruboku**, Vito uses persistent HTTP sessions and a permanent JSON memory system to outperform standard Discord AI bot implementations.

---

## 🌟 Core Features

### ⚡ Low-Latency Architecture  
Vito uses a **persistent aiohttp session**, avoiding repeated handshakes with external APIs.  
This design yields responses **200–500ms faster per message** than typical setups.

### 🧠 Persistent Memory System  
Vito remembers everything—permanently.

- **memory.json** stores user-specific data across restarts.  
- Every message triggers an automatic lookup from this file.  
- Relevant memory is injected directly into the system prompt so conversations stay consistent for weeks or months.

### 🗣️ Dual AI Engine Support  
Vito intelligently routes messages between two engines:

- **Primary (Gemini 1.5 Flash):** Fast, logical, general assistance  
- **Secondary (OpenRouter/Llama):** Accessed via `@Vito notnice` for alternative or unfiltered reasoning  
  - Default: `meta-llama/llama-3.1-8b-instruct`

### 👑 Hierarchical Access Control  
A three-tier system ensures stable resource usage:

- **Creator (Level 3):** Full system control  
- **Admins (Level 2):** Can terminate requests from standard users  
- **Users (Level 1):** Limited to managing their own tasks  

---

## ⚙️ Technical Workflow

When Vito receives a message:

1. **Parses Input:**  
   Strips mentions, identifies commands (e.g., *remember*).

2. **Assembles Context:**  
   - **RAM:** 1-hour short-term conversation history  
   - **Disk:** Permanent user memory from `memory.json`  
   - **Prompt:** Merges identity, memory, recent chat

3. **Routes API Requests:**  
   - Standard → Gemini  
   - “Not nice” → OpenRouter (Llama/other models)

4. **Manages Response:**  
   Auto-splits messages into **≤1900 characters** to satisfy Discord API limits.

---

## 🛠️ Prerequisites

- Python 3.9+
- Discord Bot Token  
- Gemini API Key  
- OpenRouter API Key  
- User/Admin IDs (enable Discord Developer Mode)

---

## 🚀 Installation Guide

### **Option 1: Automated Install (Recommended)**

1. Upload repository to your server  
2. Make installer executable:
   ```bash
   chmod +x install.sh
   ```
3. Run installation:
   ```bash
   ./install.sh
   ```
   Select **Option 2 (Install)**.  
4. Start the bot:
   ```bash
   ./install.sh
   ```
   Select **Option 1 (Start)**.

---

### **Option 2: Manual Install**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Edit `settings.json` with your tokens and model IDs.

Run the bot:

```bash
python3 main.py
```

---

## ☁️ Hosting on AlwaysData

Vito is optimized to run 24/7 on the free tier.

### 1. SSH Setup
```bash
cd Vito-bot
chmod +x install.sh
./install.sh
```

### 2. Configure Service (Web Panel)

| Setting          | Value                                                                 |
|------------------|------------------------------------------------------------------------|
| **Type**         | Custom Program                                                         |
| **Command**      | `/home/YOUR_USER/Vito-bot/venv/bin/python /home/YOUR_USER/Vito-bot/main.py` |
| **Working Dir**  | `/home/YOUR_USER/Vito-bot`                                             |
| **Monitoring**   | `/bin/true`                                                            |

### 3. Daily Auto-Restart (Cron)

Command:
```bash
pkill -f /home/YOUR_USER/Vito-bot/main.py
```

Schedule: **Daily at 23:59**

---

## 🧠 Configuration & Models

All settings are stored in `settings.json`.

### Example:
```json
{
  "creator_id": "YOUR_DISCORD_ID",
  "admin_ids": "ADMIN_ID_1, ADMIN_ID_2",
  "discord_token": "YOUR_DISCORD_TOKEN",
  "gemini_key": "YOUR_GEMINI_KEY",
  "venice_key": "YOUR_OPENROUTER_KEY",
  "model_gemini": "gemini-1.5-flash",
  "model_venice": "meta-llama/llama-3.1-8b-instruct"
}
```

To change the Llama/OpenRouter model, update `model_venice`.

Popular options:

- Uncensored: `nousresearch/hermes-3-llama-3.1-405b`
- High-intelligence: `anthropic/claude-3.5-sonnet`

---

## 💬 Commands

| Command | Example | Description |
|--------|---------|-------------|
| **Chat** | `@Vito how do I cook rice?` | Standard Gemini response |
| **Remember** | `@Vito remember I have a cat named Luna` | Saves to permanent memory |
| **Recall** | `@Vito what is my cat’s name?` | Automatically answered from memory |
| **New Chat** | `@Vito newchat` | Clears short-term RAM context |
| **Not Nice** | `@Vito notnice define anarchy` | Uses OpenRouter model |
| **Stop** | `@Vito stop` | Terminates current generation |

---

## 📂 Project Structure

```
Vito-bot/
│── main.py            # Bot logic, memory management, API routing
│── install.sh         # Automated setup
│── settings.json      # API keys + model configuration
│── memory.json        # Persistent user memory
│── requirements.txt   # Dependencies
```

---

## 📜 License

**Creator:** Yoruboku  
**License:** MIT  
**Powered By:** Google DeepMind & OpenRouter
