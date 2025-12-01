# Vito-Bot

**Tags:** `python` `discord` `github/yoruboku` `mit-license` `openrouter` `gemini`  

A fast Discord bot that uses **Gemini (gemini-2.5-flash-lite)** for conversational AI and **OpenRouter** (Venice/Dolphin models) for uncensored responses.  
Each user gets an isolated conversation history stored separately, which expires after 1 hour of inactivity.

---

## Files included
- `main.py` — bot implementation (run inside venv).  
- `install.sh` — installer (creates venv, installs deps, writes `settings.json`).  
- `requirements.txt` — Python dependencies.  
- `convos/` — per-user conversation storage (generated at runtime).  
- `memory.json` — persistent `remember` data (created at runtime).

---

## 🔐 License
This project is released under the **MIT License**. See LICENSE file.

---

## 🚀 Quick start (Linux)
1. Make the installer executable:
```bash
chmod +x install.sh
```

2. Run installer:
```bash
./install.sh
```
Follow prompts for:
- Discord Bot Token (from Developer Portal)
- Creator Discord ID (numeric)
- Admin IDs (comma separated, numeric)
- Gemini API Key (Google Generative API key)
- OpenRouter API Key (from https://openrouter.ai)

3. Start the bot:
```bash
./install.sh
```

---

## 🧩 Commands (mention the bot)
- `@bot <question>` — Ask Gemini (default).  
- `@bot notnice <question>` — Use OpenRouter model (Venice/Dolphin).  
- `@bot newchat <optional question>` — Reset conversation for your user.  
- `@bot remember <text>` — Save persistent memory for your user.  
- `@bot recall` — Recall saved memory (used by Gemini when relevant).  
- `@bot stop` — Stops current processing (admins/creator can interrupt others).

---

## 🗂 Conversation Storage
- Conversations are saved per-user in `convos/<user_id>.json`.  
- Each file contains `messages` (full conversation) and `last_used` timestamp.  
- Convos expire (deleted) after **1 hour** of inactivity automatically.  
- `newchat` clears your convo file.

---

## ⚙️ Settings (`settings.json`)
The installer creates `settings.json`. Important keys:
```json
{
  "discord_token": "YOUR_DISCORD_BOT_TOKEN",
  "creator": "YOUR_DISCORD_ID",
  "admins": ["ID1","ID2"],
  "gemini_api": "YOUR_GOOGLE_API_KEY",
  "openrouter_api": "YOUR_OPENROUTER_KEY",
  "model_gemini": "gemini-2.5-flash-lite",
  "model_venice": "cognitivecomputations/dolphin-mistral-24b-venice-edition:free"
}
```

---

## 🛡️ Notes & Tips
- If OpenRouter model rate-limits, consider adding your own provider key in OpenRouter integrations.  
- Keep your Gemini API key secure.  
- For production, run the bot under a process manager (`systemd`, `supervisor`) or in Docker.


---

## Contributions
Pull requests welcome. If you use this code in public servers, please credit `Yoruboku` and follow Discord bot rules.

