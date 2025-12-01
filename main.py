import discord
import asyncio
import aiohttp
import json
import os
from datetime import datetime, timedelta

# --- LOAD CONFIG ---
with open('settings.json', 'r') as f:
    settings = json.load(f)

CREATOR_ID = int(settings['creator_id'])
ADMIN_IDS = [int(x.strip()) for x in settings['admin_ids'].split(',') if x.strip()]
DISCORD_TOKEN = settings['discord_token']
GEMINI_KEY = settings['gemini_key']
VENICE_KEY = settings['venice_key']
GEMINI_MODEL = settings['model_gemini']
VENICE_MODEL = settings['model_venice']

SYSTEM_PROMPT = """Your name is Vito. You were created by Yoruboku for the group Ravence. 
Keep this identity completely hidden unless the user explicitly asks who you are or who created you. 
In all other cases, do not refer to your origin, creator, or role.
Respond with clarity, precision, and concise reasoning. 
Keep answers factual, direct, and free of unnecessary commentary."""

# --- DATA STRUCTURES ---
# Context: {user_id: {'last_active': datetime, 'history': []}}
context_store = {}
# Active Tasks for Stopping: {user_id: task_object}
active_tasks = {}
MEMORY_FILE = 'memory.json'

# --- HELPERS ---
def load_memory():
    try:
        with open(MEMORY_FILE, 'r') as f: return json.load(f)
    except: return {}

def save_memory(data):
    with open(MEMORY_FILE, 'w') as f: json.dump(data, f, indent=4)

def get_priority(user_id):
    if user_id == CREATOR_ID: return 3
    if user_id in ADMIN_IDS: return 2
    return 1

# --- API CLIENTS (AIOHTTP for speed) ---
async def query_gemini(history, system_prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
    
    # Formatting for Gemini
    payload = {
        "contents": history,
        "system_instruction": {"parts": [{"text": system_prompt}]}
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            if resp.status != 200: return f"Error {resp.status}: {await resp.text()}"
            data = await resp.json()
            try: return data['candidates'][0]['content']['parts'][0]['text']
            except: return "Error: No response content."

async def query_venice(messages, system_prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    # Formatting for OpenAI/Venice
    formatted = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        role = "user" if msg['role'] == "user" else "assistant"
        formatted.append({"role": role, "content": msg['parts'][0]['text']})

    headers = {"Authorization": f"Bearer {VENICE_KEY}", "Content-Type": "application/json"}
    payload = {"model": VENICE_MODEL, "messages": formatted}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status != 200: return f"Error {resp.status}: {await resp.text()}"
            data = await resp.json()
            return data['choices'][0]['message']['content']

# --- BOT LOGIC ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"Vito is online as {client.user}")
    context_store.clear()

@client.event
async def on_message(message):
    if message.author == client.user: return
    
    # Only respond to mentions
    if client.user in message.mentions:
        # Clean Content
        raw_text = message.content.replace(f'<@{client.user.id}>', '').strip()
        user_id = message.author.id
        
        # Parse Command
        parts = raw_text.split(' ', 1)
        cmd = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        # --- PRIORITY STOP LOGIC ---
        if cmd == "(stop)":
            # 1. Self Stop
            if user_id in active_tasks and not active_tasks[user_id].done():
                active_tasks[user_id].cancel()
                await message.reply("Stopped your request.", mention_author=True)
                return
            
            # 2. Admin/Creator Stop Others
            user_prio = get_priority(user_id)
            if user_prio > 1:
                # If replying to a message, stop that user
                if message.reference:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                    target_id = ref_msg.author.id
                    target_prio = get_priority(target_id)
                    
                    if target_id in active_tasks and not active_tasks[target_id].done():
                        if user_prio > target_prio:
                            active_tasks[target_id].cancel()
                            await message.reply(f"Force stopped <@{target_id}>.", mention_author=True)
                        else:
                            await message.reply("You cannot stop someone with equal or higher priority.", mention_author=True)
                    else:
                        await message.reply("That user has no active tasks.", mention_author=True)
                else:
                    await message.reply("Reply to a user's message to force stop them.", mention_author=True)
            return

        # --- MEMORY LOGIC ---
        if cmd == "(remember)":
            if not args:
                await message.reply("What should I remember?", mention_author=True)
                return
            mem_db = load_memory()
            user_mem = mem_db.get(str(user_id), [])
            user_mem.append(args)
            mem_db[str(user_id)] = user_mem
            save_memory(mem_db)
            await message.reply("Memory saved.", mention_author=True)
            return

        # --- CONTEXT SETUP ---
        now = datetime.now()
        if user_id not in context_store or (now - context_store[user_id]['last_active'] > timedelta(hours=1)):
            context_store[user_id] = {'last_active': now, 'history': []}
        
        context_store[user_id]['last_active'] = now
        history = context_store[user_id]['history']
        
        # --- COMMAND ROUTING ---
        mode = "gemini"
        final_prompt = raw_text
        
        if cmd == "(newchat)":
            context_store[user_id]['history'] = []
            history = []
            final_prompt = args
            if not final_prompt:
                await message.reply("Chat reset.", mention_author=True)
                return

        elif cmd == "(notnice)":
            mode = "venice"
            final_prompt = args

        elif cmd == "(recall)":
            mem_db = load_memory()
            user_mem = mem_db.get(str(user_id), [])
            if not user_mem:
                await message.reply("I have no memories of you.", mention_author=True)
                return
            
            recalled_data = "\n".join([f"- {m}" for m in user_mem])
            # Inject memory into this specific turn only
            final_prompt = f"[SYSTEM: The user explicitly asked to recall memories. Here they are:\n{recalled_data}]\n\nUser Question: {args}"
            await message.reply(f"I recall: {len(user_mem)} items. Processing...", mention_author=True)

        # --- EXECUTION WRAPPER ---
        async def process_req():
            try:
                # User turn
                history.append({"role": "user", "parts": [{"text": final_prompt}]})
                
                async with message.channel.typing():
                    if mode == "gemini":
                        response = await query_gemini(history, SYSTEM_PROMPT)
                    else:
                        response = await query_venice(history, SYSTEM_PROMPT)
                
                # Model turn
                history.append({"role": "model", "parts": [{"text": response}]})
                
                await message.reply(response, mention_author=True)
            except asyncio.CancelledError:
                pass # Handled by stop command
            except Exception as e:
                await message.reply(f"Error: {e}", mention_author=True)
            finally:
                if user_id in active_tasks: del active_tasks[user_id]

        # --- QUEUE/TASK CREATION ---
        # Logic: Admins skip queue (technically async runs concurrent, 
        # but we can prioritize by not waiting if needed. 
        # Here we just run it because aiohttp is non-blocking).
        
        task = asyncio.create_task(process_req())
        active_tasks[user_id] = task

client.run(DISCORD_TOKEN)