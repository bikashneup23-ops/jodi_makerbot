import os
import time
import random
import threading
from flask import Flask
import telebot

# --- Configuration ---
TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 10000))

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- Data Storage ---
# Stores active users: {chat_id: {user_id: name}}
group_members = {}
# Stores couple data: {chat_id: {"couple": (name1, name2), "expiry": timestamp}}
couple_history = {}

# --- Flask Health Check ---
@app.route('/')
def health_check():
    return "Bot is running", 200

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# --- Bot Logic ---

def get_username(user):
    """Helper to format user name or handle."""
    if user.username:
        return f"@{user.username}"
    return user.first_name

@bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'])
def track_members(message):
    """Tracks active users in groups. Ignores bots."""
    if message.from_user.is_bot:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    user_name = get_username(message.from_user)

    if chat_id not in group_members:
        group_members[chat_id] = {}
    
    # Store/Update user info
    group_members[chat_id][user_id] = user_name

@bot.message_handler(commands=['couple'])
def handle_couple(message):
    chat_id = message.chat.id
    current_time = time.time()

    # Initialize group data if not exists
    if chat_id not in group_members:
        group_members[chat_id] = {}

    # Check if we have a valid cached couple (1 hour = 3600 seconds)
    if chat_id in couple_history:
        data = couple_history[chat_id]
        if current_time < data['expiry']:
            u1, u2 = data['couple']
            bot.send_message(chat_id, f"💘 Couple of the Hour 💘\n\n{u1} ❤️ {u2}")
            return

    # Select a new couple
    members = group_members[chat_id]
    
    if len(members) < 2:
        bot.reply_to(message, "I need at least 2 active users in this group to find a couple! Send some messages first.")
        return

    # Pick 2 random unique users
    user_ids = list(members.keys())
    selected_ids = random.sample(user_ids, 2)
    u1_name = members[selected_ids[0]]
    u2_name = members[selected_ids[1]]

    # Save to history
    couple_history[chat_id] = {
        "couple": (u1_name, u2_name),
        "expiry": current_time + 3600
    }

    bot.send_message(chat_id, f"💘 Couple of the Hour 💘\n\n{u1_name} ❤️ {u2_name}")

# --- Execution ---

if __name__ == "__main__":
    # Start Flask in a background thread
    threading.Thread(target=run_flask, daemon=True).start()
    
    print(f"Bot started on port {PORT}...")
    
    # Start Telegram Polling
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Bot Polling Error: {e}")
            time.sleep(5)
