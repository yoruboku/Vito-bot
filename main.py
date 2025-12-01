import discord
import asyncio
import aiohttp
import json
import os
import logging
import sys
from datetime import datetime, timedelta

# --- PRODUCTION LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("vito.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Vito")

# --- CONFIGURATION LOADER ---
def load_config():
    try:
        with open('settings.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.critical("settings.json not found! Run install.sh first.")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.critical("settings.json is corrupted. Please check your commas and quotes.")
        sys.exit(1)

settings = load_config()

# --- SAFE CONFIG GETTERS ---
CREATOR_ID = int(settings.get('creator_id', 0) or 0)
admin_str = settings.get('admin_ids', "")
ADMIN_IDS = [int(x.strip()) for x in admin_str.split(',') if x.strip().isdigit()]

DISCORD_TOKEN = settings.get('discord_token', "").strip()
GEMINI_KEY = settings.get('gemini_key', "").strip()
VENICE_KEY = settings.get('venice_key', "").strip()

# Sanitizing Model Names (Removes 'models/' if user accidentally added it)
GEMINI_MODEL = settings.get("model_gemini", "gemini-1.5-flash").replace("models/", "")
VENICE_MODEL = settings.get("model_venice", "meta-llama/llama-3.1-8b-instruct")

if not DISCORD_TOKEN or not GEMINI_KEY:
    logger.critical("Missing API Keys in settings.json.")
    sys.exit(1)

# --- SYSTEM PROMPT ---
BASE_SYSTEM_PROMPT = """Your name is Vito. You were created by Yoruboku for the group Ravence. 
Respond with clarity, precision, and concise reasoning.
"""

# --- MEMORY SYSTEM ---
MEMORY_FILE = 'memory.json'
context_store = {}

def load_lt_memory():
    if not os.path.exists(MEMORY_FILE): return {}
    try:
        with open(MEMORY_FILE, 'r') as f: return json.load(f)
    except: return {}

def save_lt_memory(data):
    # Atomic write to prevent corruption during crash
    temp_file = MEMORY_FILE + ".tmp"
    with open(temp_file, 'w') as f: json.dump(data, f, indent=4)
    os.replace(temp_file, MEMORY_FILE)

# --- BOT CLASS ---
class VitoBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.session = None
        self.active_tasks = {}

    async def setup_hook(self):
        # Persistent Session for Speed
        self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session: await self.session.close()
        await super().close()

    async def on_ready(self):
        logger.info(f"--- VITO IS ONLINE ---")
        logger.info(f"User: {self.user}")
        logger.info(f"Gemini Model: {GEMINI_MODEL}")
        logger.info(f"Venice Model: {VENICE_MODEL}")
        context_store.clear()

    # --- ROBUST API CALLS ---
    async def call_gemini(self, history, system_instruction):
        # Correct Endpoint Construction
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
        
        payload = {
            "contents": history,
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2000
            }
        }
        
        try:
            async with self.session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Gemini API Error {response.status}: {error_text}")
                    if response.status == 404:
                        return f"Error 404: The model '{GEMINI_MODEL}' does not exist. Check settings.json."
                    return f"Gemini Error {response.status}. Check console logs."
                
                data = await response.json()
                return data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            logger.error(f"Gemini Connection Failed: {e}")
            return "Error: Could not connect to Gemini."

    async def call_openrouter(self, messages, system_instruction):
        url = "https://openrouter.ai/api/v1/chat/completions"
        
        formatted_msgs = [{"role": "system", "content": system_instruction}]
        for msg in messages:
            role = "user" if msg['role'] == "user" else "assistant"
            # Safety check for empty parts
            if msg.get('parts') and msg['parts'][0].get('text'):
                formatted_msgs.append({"role": role, "content": msg['parts'][0]['text']})

        headers = {
            "Authorization": f"Bearer {VENICE_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://discord.com",
            "X-Title": "Vito Bot"
        }
        payload = {
            "model": VENICE_MODEL,
            "messages": formatted_msgs,
            "temperature": 0.7
        }
        
        try:
            async with self.session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    text = await response.text()
                    logger.error(f"Venice API Error {response.status}: {text}")
                    return f"Venice Error {response.status}."
                data = await response.json()
                return data['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"Venice Connection Failed: {e}")
            return "Error: Could not connect to Venice."

client = VitoBot()

# --- MESSAGE HANDLING ---
@client.event
async def on_message(message):
    if message.author == client.user: return
    
    # 1. CHECK MENTIONS
    is_mentioned = client.user in message.mentions
    is_reply = (message.reference and message.reference.cached_message and 
                message.reference.cached_message.author == client.user)
    
    if not (is_mentioned or is_reply):
        return

    # 2. PARSE INPUT
    raw_content = message.content.replace(f'<@{client.user.id}>', '').strip()
    user_id = message.author.id
    
    # Split command
    parts = raw_content.split(' ', 1)
    cmd = parts[0].lower() if parts else ""
    args = parts[1] if len(parts) > 1 else ""

    # 3. STOP COMMAND (Priority)
    if cmd == "stop":
        # Check own tasks
        if user_id in client.active_tasks and not client.active_tasks[user_id].done():
            client.active_tasks[user_id].cancel()
            await message.reply("Request cancelled.", mention_author=True)
            return
        # Check admin tasks
        user_prio = 3 if user_id == CREATOR_ID else (2 if user_id in ADMIN_IDS else 1)
        if user_prio > 1 and message.reference:
            target_msg = await message.channel.fetch_message(message.reference.message_id)
            target_id = target_msg.author.id
            if target_id in client.active_tasks:
                client.active_tasks[target_id].cancel()
                await message.reply(f"Admin Force Stop applied to <@{target_id}>.", mention_author=True)
        return

    # 4. MEMORY & CONTEXT
    # Auto-refresh context after 1 hour
    now = datetime.now()
    if user_id not in context_store or (now - context_store[user_id]['last_active'] > timedelta(hours=1)):
        context_store[user_id] = {'last_active': now, 'history': []}
    context_store[user_id]['last_active'] = now

    memories = load_lt_memory()
    user_mem = memories.get(str(user_id), [])

    # 5. COMMAND ROUTING
    mode = "gemini"
    final_prompt = raw_content

    if cmd == "newchat":
        context_store[user_id]['history'] = []
        await message.reply("Context cleared.", mention_author=True)
        return

    elif cmd == "remember":
        if not args:
            await message.reply("Usage: @Vito remember [text]", mention_author=True)
            return
        timestamp = datetime.now().strftime("%Y-%m-%d")
        user_mem.append(f"[{timestamp}] {args}")
        memories[str(user_id)] = user_mem
        save_lt_memory(memories)
        await message.reply("Memory saved to database.", mention_author=True)
        return

    elif cmd in ["notnice", "venice"]:
        mode = "venice"
        final_prompt = args if args else " "

    # 6. SYSTEM PROMPT CONSTRUCTION
    current_sys = BASE_SYSTEM_PROMPT
    if user_mem:
        current_sys += "\n\n[USER MEMORIES]:\n" + "\n".join([f"- {m}" for m in user_mem])

    # 7. ASYNC EXECUTION
    async def process_request():
        try:
            async with message.channel.typing():
                history = context_store[user_id]['history']
                history.append({"role": "user", "parts": [{"text": final_prompt}]})
                
                # API Call
                if mode == "gemini":
                    response_text = await client.call_gemini(history, current_sys)
                else:
                    response_text = await client.call_openrouter(history, current_sys)
                
                # Update History
                history.append({"role": "model", "parts": [{"text": response_text}]})
                
                # Split & Send
                if len(response_text) > 2000:
                    chunks = [response_text[i:i+1900] for i in range(0, len(response_text), 1900)]
                    await message.reply(chunks[0], mention_author=True)
                    for chunk in chunks[1:]:
                        await message.channel.send(chunk)
                        await asyncio.sleep(0.3)
                else:
                    await message.reply(response_text, mention_author=True)
        
        except asyncio.CancelledError:
            logger.info(f"Task cancelled for user {user_id}")
        except Exception as e:
            logger.error(f"Unexpected Error: {e}")
            await message.reply(f"Critical Error: {e}")
        finally:
            if user_id in client.active_tasks:
                del client.active_tasks[user_id]

    # Register Task
    task = asyncio.create_task(process_request())
    client.active_tasks[user_id] = task

# --- START ---
client.run(DISCORD_TOKEN)