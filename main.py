import os
import time
import random
import requests
from flask import Flask, request
import telebot

# --- Configuration ---
TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_URL")
GITHUB_USER = os.environ.get("GITHUB_USER")
GITHUB_REPO = os.environ.get("GITHUB_REPO")
PORT = int(os.environ.get("PORT", 10000))

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- Data Storage ---
group_members = {}
couple_history = {}

# --- Dare Data ---
def get_dare_urls():
    base = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main"
    return [
        {"text": "💍 Dare: {} must PROPOSE to {} right now in the group!", "image": f"{base}/propose.png"},
        {"text": "🤗 Dare: {} must HUG {} right now in the group!", "image": f"{base}/hug.png"},
        {"text": "💋 Dare: {} must KISS {} right now in the group!", "image": f"{base}/kiss.png"},
        {"text": "💒 Dare: {} must MARRY {} right now in the group!", "image": f"{base}/marry.png"},
    ]

# --- Helper ---
def get_username(user):
    if user.username:
        return f"@{user.username}"
    return user.first_name

# --- Auto fetch group members ---
def fetch_group_members(chat_id):
    try:
        # Get admin list first (always works)
        admins = bot.get_chat_administrators(chat_id)
        if chat_id not in group_members:
            group_members[chat_id] = {}
        for admin in admins:
            if not admin.user.is_bot:
                group_members[chat_id][admin.user.id] = get_username(admin.user)
        print(f"Fetched {len(group_members[chat_id])} admins for chat {chat_id}")
    except Exception as e:
        print(f"Error fetching members: {e}")

# --- /couple command ---
@bot.message_handler(commands=['couple'])
def handle_couple(message):
    print(f"COUPLE CMD from chat_id:{message.chat.id} type:{message.chat.type}")

    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "❌ This command only works in group chats!")
        return

    chat_id = message.chat.id
    current_time = time.time()

    # Auto-register the person who sent the command
    if chat_id not in group_members:
        group_members[chat_id] = {}
    group_members[chat_id][message.from_user.id] = get_username(message.from_user)

    # Try to fetch more members automatically
    fetch_group_members(chat_id)

    # Return cached couple if still within 1 hour
    if chat_id in couple_history:
        data = couple_history[chat_id]
        if current_time < data['expiry']:
            u1, u2 = data['couple']
            dare = data['dare']
            remaining = int((data['expiry'] - current_time) / 60)
            caption = (
                f"💘 Couple of the Hour 💘\n\n"
                f"{u1} ❤️ {u2}\n\n"
                f"{dare['text'].format(u1, u2)}\n\n"
                f"🕐 Refreshes in {remaining} minute(s)"
            )
            bot.send_photo(chat_id, dare['image'], caption=caption)
            return

    members = group_members[chat_id]

    if len(members) < 2:
        bot.reply_to(
            message,
            "👥 I need at least 2 active members!\nHave others send a message in the group first, then try again."
        )
        return

    # Pick 2 random members
    user_ids = list(members.keys())
    selected_ids = random.sample(user_ids, 2)
    u1_name = members[selected_ids[0]]
    u2_name = members[selected_ids[1]]

    # Pick random dare
    dare = random.choice(get_dare_urls())

    # Cache for 1 hour
    couple_history[chat_id] = {
        "couple": (u1_name, u2_name),
        "dare": dare,
        "expiry": current_time + 3600
    }

    caption = (
        f"💘 Couple of the Hour 💘\n\n"
        f"{u1_name} ❤️ {u2_name}\n\n"
        f"{dare['text'].format(u1_name, u2_name)}\n\n"
        f"🕐 This couple refreshes in 1 hour!"
    )

    bot.send_photo(chat_id, dare['image'], caption=caption)

# --- Track every message ---
@bot.message_handler(func=lambda message: True)
def track_members(message):
    if message.from_user.is_bot:
        return
    if message.chat.type not in ['group', 'supergroup']:
        return
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = get_username(message.from_user)
    if chat_id not in group_members:
        group_members[chat_id] = {}
    group_members[chat_id][user_id] = user_name

# --- Webhook route ---
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_str = request.get_data(as_text=True)
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'ok', 200

# --- Health check ---
@app.route('/')
def health_check():
    return "Bot is running!", 200

# --- Setup webhook ---
def set_webhook():
    webhook_url = f"{RENDER_URL}/{TOKEN}"
    requests.get(
        f"https://api.telegram.org/bot{TOKEN}/deleteWebhook?drop_pending_updates=true",
        timeout=10
    )
    time.sleep(2)
    result = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={webhook_url}",
        timeout=10
    )
    print(f"Webhook set: {result.json()}")

# --- Start ---
if __name__ == "__main__":
    print(f"TOKEN loaded: {bool(TOKEN)}")
    print(f"RENDER_URL: {RENDER_URL}")
    set_webhook()
    print("Bot is starting in webhook mode...")
    app.run(host="0.0.0.0", port=PORT)
