import os
import time
import random
import json
import threading
import requests
from flask import Flask, request
from flask_cors import CORS
import telebot
from telebot import types
from datetime import datetime

# --- Configuration ---
TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_URL")
GITHUB_USER = os.environ.get("GITHUB_USER")
GITHUB_REPO = os.environ.get("GITHUB_REPO")
PORT = int(os.environ.get("PORT", 10000))
DATA_FILE = "data.json"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
CORS(app)

# --- Load/Save Data ---
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                return (
                    data.get("luck", {}),
                    data.get("command_stats", {}),
                    set(data.get("unique_users", []))
                )
        except:
            pass
    return {}, {}, set()

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({
            "luck": luck_history,
            "command_stats": command_stats,
            "unique_users": list(unique_users)
        }, f)

luck_history, command_stats, unique_users = load_data()
print(f"Loaded {len(unique_users)} unique users from file")

# --- Image URLs ---
def get_base():
    return f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main"

# --- Luck Ranges ---
LUCK_RANGES = [
    {"min": 0,  "max": 10,  "image": "7luck.png",  "msg": "Don't even try today ☠️"},
    {"min": 11, "max": 20,  "image": "14luck.png", "msg": "Just survive the day 💀"},
    {"min": 21, "max": 30,  "image": "26luck.png", "msg": "Not looking great 😕"},
    {"min": 31, "max": 40,  "image": "38luck.png", "msg": "Could be worse 😐"},
    {"min": 41, "max": 50,  "image": "47luck.png", "msg": "Don't expect miracles 🤷‍♂️"},
    {"min": 51, "max": 60,  "image": "55luck.png", "msg": "Not bad actually 🙂"},
    {"min": 61, "max": 70,  "image": "67luck.png", "msg": "Things are lowkey working out 😎"},
    {"min": 71, "max": 80,  "image": "74luck.png", "msg": "Things going your way ✨"},
    {"min": 81, "max": 90,  "image": "88luck.png", "msg": "Go take risks 🔥"},
    {"min": 91, "max": 100, "image": "96luck.png", "msg": "Main character day 👑"},
]

def get_luck_range(percent):
    for r in LUCK_RANGES:
        if r["min"] <= percent <= r["max"]:
            return r
    return LUCK_RANGES[-1]

# --- Helper ---
def get_username(user):
    if user.username:
        return f"@{user.username}"
    return user.first_name

def today_str():
    return datetime.utcnow().strftime("%Y-%m-%d")

# --- Owner ---
OWNER_ID = 1245270119

# --- Caches ---
horoscope_cache = {}
awaiting_cookies = set()

# --- Stream Data ---
stream_data = {}

# --- Debounced save ---
_save_pending = False
def save_data_async():
    global _save_pending
    if _save_pending:
        return
    _save_pending = True
    def do_save():
        global _save_pending
        time.sleep(10)
        save_data()
        _save_pending = False
    threading.Thread(target=do_save, daemon=True).start()

# --- Track command usage ---
def track_command(cmd, user_id=None):
    command_stats[cmd] = command_stats.get(cmd, 0) + 1
    if user_id is not None:
        unique_users.add(user_id)
    save_data_async()

# --- Periodic memory cleanup ---
def memory_cleanup():
    while True:
        time.sleep(3600)
        try:
            horoscope_cache.clear()
            print("[CLEANUP] Memory cleanup done")
        except Exception as e:
            print(f"[CLEANUP] Error: {e}")

# ============================================================
# FLASK ROUTES
# ============================================================

@app.route('/favicon.ico')
@app.route('/favicon.png')
def favicon():
    return '', 204

@app.route('/')
def health_check():
    return "Bot is running!", 200

@app.route('/stream-url')
def get_stream_url():
    channel = request.args.get('id', '').lower()
    url = stream_data.get(channel, "")
    return {"url": url}

# ============================================================
# BOT HANDLERS
# ============================================================

@bot.message_handler(commands=['start'])
def handle_start(message):
    track_command("start", message.from_user.id)
    owner_extra = ""
    if message.from_user.id == OWNER_ID:
        owner_extra = "\n\n🛠️ *Owner Commands:*\n📢 /broadcast — Send announcement\n📊 /stats — Bot statistics"
    bot.send_message(
        message.chat.id,
        "👋 Hey! I'm *Hourlyship Bot* 💘\n\n"
        "Here's what I can do:\n\n"
        "🎬 /stream — Match live streaming\n"
        "🍀 /luck — Check your daily luck score\n"
        "🔮 /horoscope — Get your zodiac horoscope\n"
        "🤖 /humanizer — Check if text is AI generated\n"
        "🦠 /malware — Scan file or URL for malware\n"
        "🌐 /translate — Translate text to English\n"
        "📝 /plagiarism — Check text for plagiarism\n"
        f"🍪 /cookies — Convert cookies format{owner_extra}\n\n"
        "➕ Add me to your group and let the fun begin!",
        parse_mode='Markdown'
    )
    if message.chat.type == 'private':
        handle_stream(message)

@bot.message_handler(commands=['mygroups'])
def handle_mygroups(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Owner only!")
        return
    bot.reply_to(message, "ℹ️ Member tracking has been disabled to save memory.")

@bot.message_handler(commands=['stats'])
def handle_stats(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ This command is only for the bot owner!")
        return
    if not command_stats:
        bot.reply_to(message, "No stats yet!")
        return
    sorted_stats = sorted(command_stats.items(), key=lambda x: x[1], reverse=True)
    text = "📊 Bot Command Stats\n\n"
    for cmd, count in sorted_stats:
        text += f"/{cmd} — {count} uses\n"
    total = sum(command_stats.values())
    text += f"\n🔢 Total commands used: {total}"
    text += f"\n👤 Unique users: {len(unique_users)}"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['usercount'])
def handle_usercount(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Owner only!")
        return
    bot.reply_to(message, f"👤 Total unique users: {len(unique_users)}")

# --- Cookies converter ---
def parse_netscape_cookies(text):
    cookies = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 7:
            parts = line.split()
        if len(parts) != 7:
            continue
        domain, include_sub, path, secure, expiry, name, value = parts
        cookies.append({
            "domain": domain, "name": name, "value": value,
            "path": path, "secure": secure.upper() == "TRUE",
            "httpOnly": False,
            "expirationDate": int(expiry) if expiry.isdigit() else None
        })
    return cookies

def send_cookies_json(message, text):
    try:
        cookies_json = parse_netscape_cookies(text)
        if not cookies_json:
            bot.reply_to(message, "❌ Couldn't parse any cookies.")
            return
        cookie_line = "; ".join(f"{c['name']}={c['value']}" for c in cookies_json)
        reply = f"✅ Converted! {len(cookies_json)} cookies found.\n\n`{cookie_line}`"
        if len(reply) > 4096:
            bot.send_message(message.chat.id, f"✅ Converted! {len(cookies_json)} cookies found.")
            for i in range(0, len(cookie_line), 4000):
                bot.send_message(message.chat.id, f"`{cookie_line[i:i+4000]}`", parse_mode='Markdown')
        else:
            bot.send_message(message.chat.id, reply, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, "❌ Failed to convert cookies.")

@bot.message_handler(commands=['cookies'])
def handle_cookies_command(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Owner only!")
        return
    track_command("cookies", message.from_user.id)
    awaiting_cookies.add(message.from_user.id)
    bot.reply_to(message, "🍪 Send cookies.txt file or paste raw cookie text:", parse_mode='Markdown')

@bot.message_handler(content_types=['document'], func=lambda m: m.from_user.id in awaiting_cookies)
def handle_cookies_file(message):
    user_id = message.from_user.id
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        text = downloaded.decode('utf-8', errors='ignore')
        send_cookies_json(message, text)
    except Exception as e:
        bot.reply_to(message, "❌ Failed to read the file.")
    finally:
        awaiting_cookies.discard(user_id)

@bot.message_handler(content_types=['text'], func=lambda m: m.from_user.id in awaiting_cookies)
def handle_cookies_text(message):
    send_cookies_json(message, message.text)
    awaiting_cookies.discard(message.from_user.id)

@bot.message_handler(commands=['broadcast'])
def handle_broadcast(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Owner only!")
        return
    bot.reply_to(message, "⚠️ Broadcast disabled — member tracking removed to save memory.")

@bot.message_handler(commands=['setstream'])
def handle_setstream(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Owner only!")
        return
    parts = message.text.split(None, 2)
    if len(parts) < 3:
        bot.reply_to(message, "❌ Usage: /setstream <id> <url>")
        return
    channel_id = parts[1].lower()
    stream_data[channel_id] = parts[2].strip()
    bot.reply_to(message, f"✅ Stream updated!\n\n🔗 ID: `{channel_id}`", parse_mode='Markdown')

@bot.message_handler(commands=['clearstream'])
def handle_clearstream(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Owner only!")
        return
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        bot.reply_to(message, "❌ Usage: /clearstream <id>")
        return
    channel_id = parts[1].strip().lower()
    if channel_id in stream_data:
        del stream_data[channel_id]
        bot.reply_to(message, f"✅ Stream `{channel_id}` removed!", parse_mode='Markdown')
    else:
        bot.reply_to(message, f"❌ No stream found with id `{channel_id}`", parse_mode='Markdown')

@bot.message_handler(commands=['liststreams'])
def handle_liststreams(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Owner only!")
        return
    if not stream_data:
        bot.reply_to(message, "📭 No active streams.")
        return
    text = "📺 Active Streams:\n\n"
    for cid, url in stream_data.items():
        text += f"🔗 `{cid}` → {url}\n"
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['syncevents'])
def handle_syncevents(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Owner only!")
        return
    msg = bot.reply_to(message, "📋 Paste the JSON from https://embed.cx/api/events:")
    bot.register_next_step_handler(msg, process_syncevents)

def process_syncevents(message):
    if message.from_user.id != OWNER_ID:
        return
    try:
        data = json.loads(message.text.strip())
        events = data.get("events", [])
        if not events:
            bot.reply_to(message, "❌ No events found in the JSON.")
            return
        added = []
        for event in events:
            if not is_target_match(event):
                continue
            embed_url = event.get("embed_url", "")
            if not embed_url:
                continue
            channel_id = get_channel_id(event)
            stream_data[channel_id] = embed_url
            added.append(f"✅ {event.get('match')} → `{channel_id}`")
        if not added:
            bot.reply_to(message, "⚠️ No target matches found in JSON.")
            return
        STREAM_PAGE = "https://sportzyhub.pages.dev"
        result = f"✅ *Synced {len(added)} stream(s)*\n\n"
        for a in added:
            result += f"{a}\n"
        result += f"\n🌐 Access via:\n"
        for channel_id in [a.split('`')[1] for a in added]:
            result += f"`{STREAM_PAGE}/?id={channel_id}`\n"
        bot.reply_to(message, result, parse_mode='Markdown')
    except json.JSONDecodeError:
        bot.reply_to(message, "❌ Invalid JSON!")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)[:200]}")

@bot.message_handler(commands=['stream'])
def handle_stream(message):
    track_command("stream", message.from_user.id)
    if not stream_data:
        bot.reply_to(message, "⚠️ No streams are currently active. Check back later!")
        return
    STREAM_PAGE = "https://sportzyhub.pages.dev"
    text = "🎬 *Active Streams*\n\n"
    for cid in stream_data.keys():
        text += f"📺 {cid} → {STREAM_PAGE}/?id={cid}\n"
    text += "\n⚠️ Links will be deleted in 15 minutes!\n📌 Forward to Saved Messages to keep them."
    if message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "📩 Check your DM for stream links!")
        try:
            sent = bot.send_message(message.from_user.id, text, parse_mode='Markdown')
            def delete_msg(chat_id, msg_id):
                time.sleep(900)
                try:
                    bot.delete_message(chat_id, msg_id)
                except:
                    pass
            threading.Thread(target=delete_msg, args=[message.from_user.id, sent.message_id], daemon=True).start()
        except Exception as e:
            bot.reply_to(message, f"⚠️ Couldn't DM you! Start the bot first 👉 @{bot.get_me().username}")
    else:
        sent = bot.send_message(message.chat.id, text, parse_mode='Markdown')
        def delete_msg_dm(chat_id, msg_id):
            time.sleep(900)
            try:
                bot.delete_message(chat_id, msg_id)
            except:
                pass
        threading.Thread(target=delete_msg_dm, args=[message.chat.id, sent.message_id], daemon=True).start()

@bot.message_handler(commands=['luck'])
def handle_luck(message):
    track_command("luck", message.from_user.id)
    user_id = str(message.from_user.id)
    username = get_username(message.from_user)
    today = today_str()
    if user_id in luck_history and luck_history[user_id]["date"] == today:
        percent = luck_history[user_id]["percent"]
    else:
        percent = random.choice([7, 14, 26, 38, 47, 55, 67, 74, 88, 96])
        luck_history[user_id] = {"percent": percent, "date": today}
        save_data_async()
    luck = get_luck_range(percent)
    image_url = f"{get_base()}/{luck['image']}"
    caption = f"🍀 Luck Check for {username}\n\nYour luck today: {percent}% — {luck['msg']}"
    bot.send_photo(message.chat.id, image_url, caption=caption)

@bot.message_handler(commands=['horoscope'])
def handle_horoscope(message):
    track_command("horoscope", message.from_user.id)
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("♈ Aries", callback_data=f"horo_{message.from_user.id}_aries"),
        types.InlineKeyboardButton("♉ Taurus", callback_data=f"horo_{message.from_user.id}_taurus"),
        types.InlineKeyboardButton("♊ Gemini", callback_data=f"horo_{message.from_user.id}_gemini")
    )
    markup.row(
        types.InlineKeyboardButton("♋ Cancer", callback_data=f"horo_{message.from_user.id}_cancer"),
        types.InlineKeyboardButton("♌ Leo", callback_data=f"horo_{message.from_user.id}_leo"),
        types.InlineKeyboardButton("♍ Virgo", callback_data=f"horo_{message.from_user.id}_virgo")
    )
    markup.row(
        types.InlineKeyboardButton("♎ Libra", callback_data=f"horo_{message.from_user.id}_libra"),
        types.InlineKeyboardButton("♏ Scorpio", callback_data=f"horo_{message.from_user.id}_scorpio"),
        types.InlineKeyboardButton("♐ Sagittarius", callback_data=f"horo_{message.from_user.id}_sagittarius")
    )
    markup.row(
        types.InlineKeyboardButton("♑ Capricorn", callback_data=f"horo_{message.from_user.id}_capricorn"),
        types.InlineKeyboardButton("♒ Aquarius", callback_data=f"horo_{message.from_user.id}_aquarius"),
        types.InlineKeyboardButton("♓ Pisces", callback_data=f"horo_{message.from_user.id}_pisces")
    )
    bot.send_message(message.chat.id, f"🔮 {get_username(message.from_user)}, choose your zodiac sign:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    data = call.data
    if data.startswith("horo_"):
        parts = data.split("_")
        user_id = int(parts[1])
        sign = parts[2]
        today = today_str()
        if call.from_user.id != user_id:
            bot.answer_callback_query(call.id, "❌ This is not your horoscope request!")
            return
        bot.answer_callback_query(call.id, f"Fetching {sign.capitalize()} horoscope...")
        cache_key = str(user_id)
        if cache_key in horoscope_cache and horoscope_cache[cache_key]["date"] == today and horoscope_cache[cache_key]["sign"] == sign:
            horoscope_text = horoscope_cache[cache_key]["text"]
        else:
            try:
                response = requests.get(
                    f"https://horoscope-app-api.vercel.app/api/v1/get-horoscope/daily?sign={sign}&day=today",
                    timeout=10
                )
                data_json = response.json()
                horoscope_data = data_json.get("data", {})
                if isinstance(horoscope_data, str):
                    horoscope_text = f"🔮 {horoscope_data}"
                elif isinstance(horoscope_data, dict):
                    reading = (
                        horoscope_data.get("horoscope_data") or
                        horoscope_data.get("description") or
                        horoscope_data.get("horoscope") or
                        "No horoscope available"
                    )
                    date_str = horoscope_data.get("date", today)
                    horoscope_text = f"📅 Date: {date_str}\n\n🔮 {reading}"
                else:
                    horoscope_text = "❌ Unexpected API response format."
                horoscope_cache[cache_key] = {"sign": sign, "date": today, "text": horoscope_text}
            except Exception as e:
                bot.send_message(call.message.chat.id, "❌ Could not fetch horoscope. Try again later!")
                return
        username = get_username(call.from_user)
        sign_emojis = {
            "aries": "♈", "taurus": "♉", "gemini": "♊", "cancer": "♋",
            "leo": "♌", "virgo": "♍", "libra": "♎", "scorpio": "♏",
            "sagittarius": "♐", "capricorn": "♑", "aquarius": "♒", "pisces": "♓"
        }
        emoji = sign_emojis.get(sign, "🔮")
        bot.send_message(call.message.chat.id, f"{emoji} {sign.capitalize()} Horoscope for {username}\n\n{horoscope_text}")
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except:
            pass

# --- /humanizer command ---
@bot.message_handler(commands=['humanizer'])
def handle_humanizer(message):
    track_command("humanizer", message.from_user.id)
    msg = bot.reply_to(message, "📝 Send the text you want to check:")
    bot.register_next_step_handler(msg, process_humanizer_text)

def process_humanizer_text(message):
    text = message.text.strip() if message.text else None
    if not text or len(text) < 30:
        bot.reply_to(message, "❌ Text too short! Please send at least 30 characters.")
        return
    status = bot.reply_to(message, "🔍 Analyzing text...")
    def do_detect():
        try:
            sapling_key = os.environ.get("SAPLING_API_KEY", "")
            if not sapling_key:
                bot.edit_message_text("❌ API key not configured.", message.chat.id, status.message_id)
                return
            response = requests.post(
                "https://api.sapling.ai/api/v1/aidetect",
                json={"key": sapling_key, "text": text},
                timeout=15
            )
            result = response.json()
            score = result.get("score", None)
            if score is None:
                error_msg = result.get("msg", result.get("message", "Unknown error"))
                bot.edit_message_text(f"❌ Detection failed: {error_msg}", message.chat.id, status.message_id)
                return
            ai_percent = int(score * 100)
            human_percent = 100 - ai_percent
            if ai_percent >= 70:
                verdict = "🤖 Very likely AI-generated"
                emoji = "🔴"
            elif ai_percent >= 40:
                verdict = "⚠️ Possibly AI-generated"
                emoji = "🟡"
            else:
                verdict = "✅ Likely human-written"
                emoji = "🟢"
            bot.edit_message_text(
                f"{emoji} *AI Detection Result*\n\n"
                f"🤖 AI Generated: *{ai_percent}%*\n"
                f"👤 Human Written: *{human_percent}%*\n\n"
                f"Verdict: {verdict}",
                message.chat.id, status.message_id, parse_mode='Markdown'
            )
        except Exception as e:
            bot.edit_message_text(f"❌ Error: {str(e)[:200]}", message.chat.id, status.message_id)
    threading.Thread(target=do_detect, daemon=True).start()

# --- /malware command ---
@bot.message_handler(commands=['malware'])
def handle_malware(message):
    track_command("malware", message.from_user.id)
    msg = bot.reply_to(message, "📁 Send a file (max 20MB) or paste a URL to scan:")
    bot.register_next_step_handler(msg, process_malware_input)

def process_malware_input(message):
    vt_key = os.environ.get("VIRUSTOTAL_API_KEY", "")
    if message.text and (message.text.startswith("http://") or message.text.startswith("https://")):
        url = message.text.strip()
        status = bot.reply_to(message, "🔍 Submitting URL to VirusTotal...")
        def scan_url():
            try:
                resp = requests.post(
                    "https://www.virustotal.com/api/v3/urls",
                    headers={"x-apikey": vt_key},
                    data={"url": url}, timeout=15
                )
                analysis_id = resp.json().get("data", {}).get("id")
                if not analysis_id:
                    bot.edit_message_text("❌ Submission failed.", message.chat.id, status.message_id)
                    return
                bot.edit_message_text("🔬 Scanning URL...", message.chat.id, status.message_id)
                for attempt in range(18):
                    time.sleep(5)
                    if attempt == 6:
                        try:
                            bot.edit_message_text("🔬 Still scanning...", message.chat.id, status.message_id)
                        except:
                            pass
                    result_resp = requests.get(
                        f"https://www.virustotal.com/api/v3/analyses/{analysis_id}",
                        headers={"x-apikey": vt_key}, timeout=15
                    )
                    result = result_resp.json()
                    if result.get("data", {}).get("attributes", {}).get("status") == "completed":
                        stats = result["data"]["attributes"]["stats"]
                        malicious = stats.get("malicious", 0)
                        suspicious = stats.get("suspicious", 0)
                        harmless = stats.get("harmless", 0)
                        total = malicious + suspicious + harmless + stats.get("undetected", 0)
                        verdict = "🔴 *Malicious URL!*" if malicious > 0 else "🟡 *Suspicious*" if suspicious > 0 else "🟢 *URL is safe*"
                        bot.edit_message_text(
                            f"{verdict}\n\n🌐 `{url}`\n\n🔴 {malicious}/{total}\n🟡 {suspicious}/{total}\n✅ {harmless}/{total}",
                            message.chat.id, status.message_id, parse_mode='Markdown'
                        )
                        return
                bot.edit_message_text("⏰ Scan timed out.", message.chat.id, status.message_id)
            except Exception as e:
                bot.edit_message_text(f"❌ Error: {str(e)[:200]}", message.chat.id, status.message_id)
        threading.Thread(target=scan_url, daemon=True).start()
    elif message.document:
        file_size_mb = message.document.file_size / (1024 * 1024)
        if file_size_mb > 20:
            bot.reply_to(message, f"❌ File too large ({file_size_mb:.1f}MB). Max 20MB.")
            return
        status = bot.reply_to(message, "⏳ Downloading file...")
        def scan_file():
            try:
                file_info = bot.get_file(message.document.file_id)
                file_data = requests.get(f"https://api.telegram.org/file/bot{TOKEN}/{file_info.file_path}", timeout=60).content
                bot.edit_message_text("🔍 Uploading to VirusTotal...", message.chat.id, status.message_id)
                upload_resp = requests.post(
                    "https://www.virustotal.com/api/v3/files",
                    headers={"x-apikey": vt_key},
                    files={"file": (message.document.file_name, file_data)}, timeout=60
                )
                analysis_id = upload_resp.json().get("data", {}).get("id")
                if not analysis_id:
                    bot.edit_message_text("❌ Upload failed.", message.chat.id, status.message_id)
                    return
                bot.edit_message_text("🔬 Scanning...", message.chat.id, status.message_id)
                for attempt in range(18):
                    time.sleep(5)
                    if attempt == 6:
                        try:
                            bot.edit_message_text("🔬 Still scanning...", message.chat.id, status.message_id)
                        except:
                            pass
                    result_resp = requests.get(
                        f"https://www.virustotal.com/api/v3/analyses/{analysis_id}",
                        headers={"x-apikey": vt_key}, timeout=15
                    )
                    result = result_resp.json()
                    if result.get("data", {}).get("attributes", {}).get("status") == "completed":
                        stats = result["data"]["attributes"]["stats"]
                        malicious = stats.get("malicious", 0)
                        suspicious = stats.get("suspicious", 0)
                        undetected = stats.get("undetected", 0)
                        total = malicious + suspicious + undetected + stats.get("harmless", 0)
                        verdict = "🔴 *MALWARE DETECTED!*" if malicious > 0 else "🟡 *Suspicious*" if suspicious > 0 else "🟢 *File is clean*"
                        bot.edit_message_text(
                            f"{verdict}\n\n📄 `{message.document.file_name}`\n📦 {file_size_mb:.1f}MB\n\n🔴 {malicious}/{total}\n🟡 {suspicious}/{total}\n✅ {undetected}/{total}",
                            message.chat.id, status.message_id, parse_mode='Markdown'
                        )
                        return
                bot.edit_message_text("⏰ Scan timed out.", message.chat.id, status.message_id)
            except Exception as e:
                bot.edit_message_text(f"❌ Error: {str(e)[:200]}", message.chat.id, status.message_id)
        threading.Thread(target=scan_file, daemon=True).start()
    else:
        bot.reply_to(message, "❌ Send a file or URL starting with http:// or https://")

# --- /translate command ---
@bot.message_handler(commands=['translate'])
def handle_translate(message):
    track_command("translate", message.from_user.id)
    msg = bot.reply_to(message, "🌐 Send the text to translate to English:")
    bot.register_next_step_handler(msg, process_translate)

def process_translate(message):
    text = message.text.strip() if message.text else None
    if not text:
        bot.reply_to(message, "❌ Please send a valid text message.")
        return
    status = bot.reply_to(message, "🔄 Translating...")
    def do_translate():
        try:
            from deep_translator import GoogleTranslator
            translated = GoogleTranslator(source='auto', target='en').translate(text)
            bot.edit_message_text(f"🇬🇧 *English Translation:*\n\n{translated}", message.chat.id, status.message_id, parse_mode='Markdown')
        except Exception as e:
            bot.edit_message_text(f"❌ Translation failed: {str(e)[:200]}", message.chat.id, status.message_id)
    threading.Thread(target=do_translate, daemon=True).start()

# --- /plagiarism command ---
@bot.message_handler(commands=['plagiarism'])
def handle_plagiarism(message):
    track_command("plagiarism", message.from_user.id)
    msg = bot.reply_to(message, "📝 Send the text to check for plagiarism:")
    bot.register_next_step_handler(msg, process_plagiarism)

def process_plagiarism(message):
    text = message.text.strip() if message.text else None
    if not text or len(text) < 50:
        bot.reply_to(message, "❌ Text too short! At least 50 characters needed.")
        return
    status = bot.reply_to(message, "🔍 Analyzing text for plagiarism...")
    def do_plagiarism():
        try:
            import difflib, re
            google_api_key = os.environ.get("GOOGLE_API_KEY", "")
            google_cse_id = os.environ.get("GOOGLE_CSE_ID", "")
            groq_key = os.environ.get("GROQ_API_KEY", "")
            if not google_api_key or not google_cse_id:
                bot.edit_message_text("❌ Search API not configured.", message.chat.id, status.message_id)
                return
            sentences = [s.strip() for s in text.replace('!', '.').replace('?', '.').split('.') if len(s.strip()) > 20]
            search_queries = sentences[:5]
            bot.edit_message_text("🌐 Searching online sources...", message.chat.id, status.message_id)
            found_sources = []
            for query in search_queries:
                try:
                    search_resp = requests.get(
                        "https://www.googleapis.com/customsearch/v1",
                        params={"key": google_api_key, "cx": google_cse_id, "q": query[:150], "num": 5},
                        timeout=15
                    )
                    items = search_resp.json().get("items", [])
                    for item in items:
                        url = item.get("link", "")
                        title = item.get("title", "Unknown")
                        snippet = item.get("snippet", "")
                        pagemap = item.get("pagemap", {})
                        metatags = pagemap.get("metatags", [{}])[0]
                        author = metatags.get("author", metatags.get("og:site_name", "Unknown"))
                        pub_date = metatags.get("article:published_time", metatags.get("date", "Unknown"))
                        if not any(s["url"] == url for s in found_sources):
                            similarity = difflib.SequenceMatcher(None, query.lower(), snippet.lower()).ratio()
                            word_overlap = len(set(query.lower().split()) & set(snippet.lower().split())) / max(len(set(query.lower().split())), 1)
                            found_sources.append({"url": url, "title": title, "snippet": snippet, "author": author, "pub_date": pub_date, "similarity": max(similarity, word_overlap)})
                except Exception as e:
                    continue
            found_sources.sort(key=lambda x: x["similarity"], reverse=True)
            found_sources = found_sources[:5]
            if not found_sources:
                bot.edit_message_text("✅ *Plagiarism Check Complete*\n\nNo matching sources found.\nThe text appears original.", message.chat.id, status.message_id, parse_mode='Markdown')
                return
            bot.edit_message_text("📊 Generating report...", message.chat.id, status.message_id)
            sources_summary = "\n".join([f"- Title: {s['title']}\n  URL: {s['url']}\n  Author: {s.get('author','Unknown')}\n  Date: {s.get('pub_date','Unknown')}\n  Snippet: {s['snippet'][:150]}" for s in found_sources])
            groq_resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.3-70b-versatile", "max_tokens": 1500,
                    "messages": [{"role": "user", "content": f"Plagiarism detection. TEXT:\n{text}\n\nSOURCES:\n{sources_summary}\n\nReturn ONLY valid JSON:\n{{\"plagiarism_percent\": 0-100, \"original_percent\": 0-100, \"confidence\": \"High/Medium/Low\", \"sources\": [{{\"rank\": 1, \"title\": \"\", \"url\": \"\", \"similarity_percent\": 0-100, \"match_type\": \"Exact/Near/Cited\", \"matching_text\": \"\", \"apa\": \"\", \"mla\": \"\", \"ieee\": \"\"}}], \"summary\": \"\"}}"}]
                }, timeout=30
            )
            raw = groq_resp.json()["choices"][0]["message"]["content"]
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if not json_match:
                raise Exception("Could not parse AI response")
            report = json.loads(json_match.group())
            plagiarism_pct = report.get("plagiarism_percent", 0)
            original_pct = report.get("original_percent", 100)
            confidence = report.get("confidence", "Medium")
            summary = report.get("summary", "")
            sources = report.get("sources", [])
            score_emoji = "🔴" if plagiarism_pct >= 70 else "🟡" if plagiarism_pct >= 30 else "🟢"
            output = f"{score_emoji} *Plagiarism Score: {plagiarism_pct}%*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            if sources:
                output += "📌 *Similar Sources*\n\n"
                for i, src in enumerate(sources[:3], 1):
                    output += f"*Source {i}*\n• Similarity: {src.get('similarity_percent', 0)}%\n• Match: {src.get('match_type', 'Near')}\n• Text: _{src.get('matching_text', 'N/A')[:100]}_\n• URL: {src.get('url', 'N/A')}\n• APA: `{src.get('apa', 'N/A')}`\n• MLA: `{src.get('mla', 'N/A')}`\n• IEEE: `{src.get('ieee', 'N/A')}`\n\n"
            output += f"━━━━━━━━━━━━━━━━━━━━━━\n📊 *Summary*\n\n• Original: {original_pct}%\n• Plagiarism: {plagiarism_pct}%\n• Confidence: {confidence}"
            if summary:
                output += f"\n\n_{summary}_"
            if len(output) > 4000:
                output = output[:3900] + "\n\n_...truncated_"
            bot.edit_message_text(output, message.chat.id, status.message_id, parse_mode='Markdown')
        except Exception as e:
            bot.edit_message_text(f"❌ Error: {str(e)[:200]}", message.chat.id, status.message_id)
    threading.Thread(target=do_plagiarism, daemon=True).start()

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_str = request.get_data(as_text=True)
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'ok', 200

def set_webhook():
    webhook_url = f"{RENDER_URL}/{TOKEN}"
    requests.get(f"https://api.telegram.org/bot{TOKEN}/deleteWebhook?drop_pending_updates=true", timeout=10)
    time.sleep(2)
    result = requests.get(f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}", timeout=10)
    print(f"Webhook set: {result.json()}")

# ============================================================
# AUTO STREAM WATCHER
# ============================================================

EVENTS_API = "https://embed.cx/api/events"

TARGET_MATCHES = {
    "Premier League": ["manchester city", "arsenal", "chelsea", "manchester united", "liverpool"],
    "La Liga": ["real madrid", "barcelona"]
}

active_auto_streams = {}

def slugify(text):
    return text.lower().replace(" ", "-").replace(".", "").replace("'", "")

def is_target_match(event):
    league = event.get("league", "")
    home = event.get("home", "").lower()
    away = event.get("away", "").lower()
    for target_league, teams in TARGET_MATCHES.items():
        if target_league.lower() in league.lower():
            for team in teams:
                if team in home or team in away:
                    return True
    return False

def get_channel_id(event):
    home = slugify(event.get("home", ""))
    away = slugify(event.get("away", ""))
    league = slugify(event.get("league", ""))
    return f"{league}_{home}_vs_{away}"[:40]

def auto_stream_watcher():
    print("🔄 Auto stream watcher started...")
    first_run = True
    while True:
        if not first_run:
            time.sleep(420)
        first_run = False
        try:
            print("[WATCHER] Fetching events from embed.cx...")
            resp = requests.get(
                EVENTS_API, timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://embed.cx/",
                    "Origin": "https://embed.cx"
                }
            )
            print(f"[WATCHER] Response status: {resp.status_code}")
            data = resp.json()
            events = data.get("events", [])
            print(f"[WATCHER] Total events: {len(events)}")
            live_ids = set()
            for event in events:
                event_id = event.get("id")
                status = event.get("status", "")
                embed_url = event.get("embed_url", "")
                print(f"[WATCHER] Event: {event.get('match')} | League: {event.get('league')} | Status: {status} | Target: {is_target_match(event)}")
                if not is_target_match(event):
                    continue
                channel_id = get_channel_id(event)
                if embed_url:
                    live_ids.add(event_id)
                    if event_id not in active_auto_streams:
                        stream_data[channel_id] = embed_url
                        active_auto_streams[event_id] = channel_id
                        print(f"✅ Auto-set stream: {channel_id} → {embed_url}")
            ended_ids = [eid for eid in active_auto_streams if eid not in live_ids]
            for eid in ended_ids:
                channel_id = active_auto_streams.pop(eid)
                if channel_id in stream_data:
                    del stream_data[channel_id]
                    print(f"🗑️ Auto-cleared stream: {channel_id}")
        except Exception as e:
            print(f"Auto stream watcher error: {e}")

# --- Startup ---
set_webhook()
threading.Thread(target=auto_stream_watcher, daemon=True).start()
threading.Thread(target=memory_cleanup, daemon=True).start()
print("Bot started successfully.")

if __name__ == "__main__":
    print(f"TOKEN loaded: {bool(TOKEN)}")
    print(f"RENDER_URL: {RENDER_URL}")
    app.run(host="0.0.0.0", port=PORT)
