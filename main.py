import os
import time
import random
import threading
import requests
from flask import Flask
import telebot

# --- Configuration ---
TOKEN = os.environ.get("BOT_TOKEN")
RENDER_URL = os.environ.get("RENDER_URL")  # e.g. https://jodi-makerbot.onrender.com
PORT = int(os.environ.get("PORT", 10000))

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- Data Storage ---
# {chat_id: {user_id: name}}
group_members = {}
# {chat_id: {"couple": (name1, name2), "expiry": timestamp}}
couple_history = {}

# --- Flask Health Check ---
@app.route('/')
def health_check():
    return "Bot is running!", 200

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# --- Self-Ping to prevent Render free tier sleep ---
def self_ping():
    while True:
        time.sleep(600)  # every 10 minutes
        if RENDER_URL:
            try:
                requests.get(RENDER_URL, timeout=10)
                print("Self-ping successful")
            except Exception as e:
                print(f"Self-ping failed: {e}")

# --- Helper ---
def get_username(user):
    if user.username:
        return f"@{user.username}"
    return user.first_name

# --- Track every message in group ---
@bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'])
def track_members(message):
    print(f"MSG from chat_id:{message.chat.id} type:{message.chat.type}")
    if message.from_user.is_bot:
        return
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = get_username(message.from_user)

    if chat_id not in group_members:
        group_members[chat_id] = {}

    group_members[chat_id][user_id] = user_name

# --- /couple command ---
@bot.message_handler(commands=['couple'])
def handle_couple(message):
    # Only works in groups
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "❌ This command only works in group chats!")
        return

    chat_id = message.chat.id
    current_time = time.time()

    # Auto-register the person who sent the command
    if chat_id not in group_members:
        group_members[chat_id] = {}
    group_members[chat_id][message.from_user.id] = get_username(message.from_user)

    # Return cached couple if still within 1 hour
    if chat_id in couple_history:
        data = couple_history[chat_id]
        if current_time < data['expiry']:
            u1, u2 = data['couple']
            remaining = int((data['expiry'] - current_time) / 60)
            bot.send_message(
                chat_id,
                f"💘 Couple of the Hour 💘\n\n{u1} ❤️ {u2}\n\n🕐 Refreshes in {remaining} minute(s)"
            )
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

    # Cache the couple for 1 hour
    couple_history[chat_id] = {
        "couple": (u1_name, u2_name),
        "expiry": current_time + 3600
    }

    bot.send_message(
        chat_id,
        f"💘 Couple of the Hour 💘\n\n{u1_name} ❤️ {u2_name}\n\n🕐 This couple refreshes in 1 hour!"
    )

# --- Start everything ---
if __name__ == "__main__":
    print(f"TOKEN loaded: {bool(TOKEN)}")
    print("Starting bot polling...")
    # Flask in background thread
    threading.Thread(target=run_flask, daemon=True).start()
    # Self-ping in background thread
    threading.Thread(target=self_ping, daemon=True).start()
    # Clear any existing webhook or polling conflict
    bot.remove_webhook()
    time.sleep(2)
    print("Bot is starting...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(5)
            
