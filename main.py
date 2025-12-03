import discord
import asyncio
import aiohttp
import json
import os
import logging
import sys
from datetime import datetime, timedelta

# --- PRODUCTION LOGGING SETUP ---
# Logs are written to vito.log file and stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
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

# --- CONFIG GETTERS ---
CREATOR_ID = int(settings.get('creator_id', 0) or 0)
# Handle admin_ids being empty or malformed more robustly
admin_ids_raw = settings.get('admin_ids', "")
ADMIN_IDS = [int(x.strip()) for x in str(admin_ids_raw).split(',') if x.strip().isdigit()]

DISCORD_TOKEN = settings.get('discord_token', "").strip()
GEMINI_KEY = settings.get('gemini_key', "").strip()
VENICE_KEY = settings.get('venice_key', "").strip()

# Using the stable model as per your fix
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
    except Exception as e:
        logger.error(f"Failed to load memory: {e}")
        return {}

def save_lt_memory(data):
    # Atomic write to prevent corruption during crash
    temp_file = MEMORY_FILE + ".tmp"
    try:
        with open(temp_file, 'w') as f: json.dump(data, f, indent=4)
        os.replace(temp_file, MEMORY_FILE)
    except Exception as e:
        logger.error(f"Failed to save memory: {e}")

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
        context_store.clear()

    # --- API CALLS (FAIL FAST) ---
    async def call_gemini(self, history, system_instruction, use_search=False):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
        
        payload = {
            "contents": history,
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2000
            }
        }
        
        # --- GOOGLE SEARCH GROUNDING IMPLEMENTATION ---
        if use_search:
            payload['tools'] = [{"google_search": {}}]
            # Log the specific query being searched for better debugging
            last_msg = history[-1]['parts'][0]['text'] if history else "Unknown"
            logger.info(f"Payload set with google_search tool. Query: '{last_msg}'")

        try:
            async with self.session.post(url, json=payload) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    # Log the specific API error, including the 429 status
                    logger.error(f"Gemini API FAILED ({response.status}). URL: {url}. Details: {error_text}")
                    
                    if response.status == 429:
                        return "Gemini Error 429: Rate limit exceeded. Try again later."
                    if response.status == 404:
                        return f"Gemini Error 404: Model '{GEMINI_MODEL}' not found. Check settings.json."
                    return f"Gemini Error {response.status}. Check vito.log for details."
                
                # Success path
                data = await response.json()
                
                # Check for grounded content and inform user/log source
                output_text = ""
                try:
                    output_text = data['candidates'][0]['content']['parts'][0]['text']
                    
                    # Enhanced logging to show if grounding was actually used
                    if use_search:
                        # Check if groundingMetadata exists
                        candidate = data.get('candidates', [{}])[0]
                        grounding_metadata = candidate.get('groundingMetadata')
                        
                        if grounding_metadata:
                            sources = grounding_metadata.get('groundingAttributions', [])
                            source_uris = [s['web']['uri'] for s in sources if 'web' in s and 'uri' in s['web']]
                            if source_uris:
                                logger.info(f"Search Grounding SUCCESS. Sources used: {len(source_uris)}")
                                output_text += "\n\n*(This answer was generated using current web data.)*"
                            else:
                                logger.info("Search tool requested, result returned but no specific web sources cited.")
                                # If no sources cited for a search query, it might be vague.
                                if "I cannot" in output_text or "Please specify" in output_text:
                                    output_text += "\n\n*(Tip: Try a more specific search query for better results.)*"
                        else:
                            logger.warning("Search tool requested, but no grounding metadata found in response.")
                        
                    return output_text
                    
                except (KeyError, IndexError):
                    return "Error: Gemini returned an empty response."

        except Exception as e:
            logger.error(f"Gemini Connection Failed: {e}")
            return "Error: Could not connect to Gemini."


    async def call_openrouter(self, messages, system_instruction):
        url = "https://openrouter.ai/api/v1/chat/completions"
        
        formatted_msgs = [{"role": "system", "content": system_instruction}]
        for msg in messages:
            role = "user" if msg['role'] == "user" else "assistant"
            # Ensure msg parts exists and has text before accessing
            if msg.get('parts') and len(msg['parts']) > 0 and msg['parts'][0].get('text'):
                formatted_msgs.append({"role": role, "content": msg['parts'][0]['text']})

        headers = {
            "Authorization": f"Bearer {VENICE_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://discord.com",
            "X-Title": "Vito Bot"
        }
        payload = {"model": VENICE_MODEL, "messages": formatted_msgs, "temperature": 0.7}
        
        try:
            async with self.session.post(url, headers=headers, json=payload) as response:
                    
                if response.status != 200:
                    text = await response.text()
                    logger.error(f"Venice API FAILED ({response.status}). Details: {text}")
                    
                    if response.status == 429:
                        return "Venice Error 429: Rate limit exceeded. Try again later."
                    return f"Venice Error {response.status}. Check vito.log for details."
                
                data = await response.json()
                return data['choices'][0]['message']['content']
            
        except Exception as e:
            logger.error(f"Venice Request Failed: {e}")
            return "Error: Could not connect to Venice."
        

client = VitoBot()

# --- MESSAGE HANDLING ---
def get_priority(user_id):
    if user_id == CREATOR_ID: return 3
    if user_id in ADMIN_IDS: return 2
    return 1

@client.event
async def on_message(message):
    if message.author == client.user: return
    
    is_mentioned = client.user in message.mentions
    is_reply = (message.reference and message.reference.cached_message and 
                message.reference.cached_message.author == client.user)
    
    if not (is_mentioned or is_reply): return

    # 1. PARSE INPUT
    raw_content = message.content.replace(f'<@{client.user.id}>', '').strip()
    user_id = message.author.id
    
    parts = raw_content.split(' ', 1)
    cmd = parts[0].lower() if parts else ""
    args = parts[1] if len(parts) > 1 else ""

    # 2. STOP COMMAND
    if cmd == "stop":
        if user_id in client.active_tasks and not client.active_tasks[user_id].done():
            client.active_tasks[user_id].cancel()
            await message.reply("Request cancelled.", mention_author=True)
            return
        
        user_prio = get_priority(user_id)
        if user_prio > 1 and message.reference:
            try:
                target_msg = await message.channel.fetch_message(message.reference.message_id)
                target_id = target_msg.author.id
                if target_id in client.active_tasks and get_priority(target_id) < user_prio:
                    client.active_tasks[target_id].cancel()
                    await message.reply(f"Admin Force Stop applied to <@{target_id}>.", mention_author=True)
            except Exception as e:
                logger.error(f"Error during admin stop: {e}")
        return

    # 3. CONTEXT & MEMORY SETUP
    now = datetime.now()
    if user_id not in context_store or (now - context_store[user_id]['last_active'] > timedelta(hours=1)):
        context_store[user_id] = {'last_active': now, 'history': []}
    context_store[user_id]['last_active'] = now

    memories = load_lt_memory()
    user_mem = memories.get(str(user_id), [])

    # 4. COMMAND ROUTING
    mode = "gemini"
    final_prompt = raw_content
    use_search = False # Default: No search grounding

    if cmd == "newchat":
        context_store[user_id]['history'] = []
        await message.reply("Context cleared.", mention_author=True)
        return

    elif cmd == "remember":
        if not args: return await message.reply("Usage: @Vito remember [text]", mention_author=True)
        timestamp = datetime.now().strftime("%Y-%m-%d")
        user_mem.append(f"[{timestamp}] {args}")
        memories[str(user_id)] = user_mem
        save_lt_memory(memories)
        await message.reply("Memory saved to database.", mention_author=True)
        return

    elif cmd in ["notnice", "venice"]:
        mode = "venice"
        final_prompt = args if args else " "
        
    elif cmd == "search": # NEW SEARCH COMMAND
        mode = "gemini"
        # Corrected Python ternary expression syntax
        final_prompt = args if args else "What is the news today?" 
        use_search = True # Enable search tool
        
    # 5. SYSTEM PROMPT CONSTRUCTION (for memory injection)
    current_sys = BASE_SYSTEM_PROMPT
    if user_mem:
        current_sys += "\n\n[USER MEMORIES]:\n" + "\n".join([f"- {m}" for m in user_mem])

    # 6. ASYNC EXECUTION
    async def process_request():
        try:
            async with message.channel.typing():
                history = context_store[user_id]['history']
                history.append({"role": "user", "parts": [{"text": final_prompt}]})
                
                # API Call
                if mode == "gemini":
                    # Pass search flag to call_gemini
                    response_text = await client.call_gemini(history, current_sys, use_search=use_search)
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

try:
    client.run(DISCORD_TOKEN)
except discord.HTTPException as e:
    logger.critical(f"Discord Login Failed. Check your DISCORD_TOKEN. Error: {e}")
