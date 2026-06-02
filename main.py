import os
import time
import random
import json
import requests
from flask import Flask, request
import telebot
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

# --- Load/Save Data ---
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                return (
    {int(k): v for k, v in data.get("members", {}).items()},
    {int(k): v for k, v in data.get("couples", {}).items()},
    data.get("luck", {}),
    {int(k): v for k, v in data.get("group_names", {}).items()}
                )
        except:
            pass
    return {}, {}, {}, {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({
            "members": {str(k): v for k, v in group_members.items()},
            "couples": {str(k): v for k, v in couple_history.items()},
            "luck": luck_history,
            "group_names": {str(k): v for k, v in group_names.items()}
        }, f)

# --- Load existing data on startup ---
group_members, couple_history, luck_history, group_names = load_data()
used_expose = {}
print(f"Loaded {sum(len(v) for v in group_members.values())} members from file")

# --- Image URLs ---
def get_base():
    return f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main"

def get_dare_urls():
    base = get_base()
    return [
        {"text": "💍 Dare: {} must PROPOSE to {} right now in the group!", "image": f"{base}/propose.png"},
        {"text": "🤗 Dare: {} must HUG {} right now in the group!", "image": f"{base}/hug.png"},
        {"text": "💋 Dare: {} must KISS {} right now in the group!", "image": f"{base}/kiss.png"},
        {"text": "💒 Dare: {} must MARRY {} right now in the group!", "image": f"{base}/marry.png"},
    ]

# --- Luck Ranges ---
LUCK_RANGES = [
    {"min": 0,  "max": 10,  "image": "7luck.png",  "label": "💀 Terrible",      "msg": "Don't even try today ☠️"},
    {"min": 11, "max": 20,  "image": "14luck.png", "label": "😭 Very Bad",       "msg": "Just survive the day 💀"},
    {"min": 21, "max": 30,  "image": "26luck.png", "label": "😕 Bad",            "msg": "Not looking great 😕"},
    {"min": 31, "max": 40,  "image": "38luck.png", "label": "😐 Low",            "msg": "Could be worse 😐"},
    {"min": 41, "max": 50,  "image": "47luck.png", "label": "🤷 Meh",            "msg": "Don't expect miracles 🤷‍♂️"},
    {"min": 51, "max": 60,  "image": "55luck.png", "label": "🙂 Slightly Good",  "msg": "Not bad actually 🙂"},
    {"min": 61, "max": 70,  "image": "67luck.png", "label": "😎 Good",           "msg": "Things are lowkey working out 😎"},
    {"min": 71, "max": 80,  "image": "74luck.png", "label": "✨ Very Good",      "msg": "Things going your way ✨"},
    {"min": 81, "max": 90,  "image": "88luck.png", "label": "🔥 Lucky",          "msg": "Go take risks 🔥"},
    {"min": 91, "max": 100, "image": "96luck.png", "label": "👑 OP Luck",        "msg": "Main character day 👑"},
]

def get_luck_range(percent):
    for r in LUCK_RANGES:
        if r["min"] <= percent <= r["max"]:
            return r
    return LUCK_RANGES[-1]

# --- Boredom Suggestions ---
BOREDOM_SUGGESTIONS = [
    "Go outside and count how many dogs you see 🐕👀",
    "Open YouTube and click the 3rd recommended video only ▶️🎯",
    "Scroll your gallery and revisit old memories 🖼️📱",
    "Stare at the ceiling and rethink your life choices 🧠😶‍🌫️",
    "Try to balance on one leg for 30 seconds 🦵⏳",
    "Go check what your neighbors are doing (not in a creepy way 😄) 🏠👀",
    "Open Netflix and pick the weirdest title you see 🍿🤨",
    "Watch old cartoons 📺🧸",
    "Exist… just exist… that's enough 😌🌍",
    "Check your screen time and feel guilty 📱⏱️😬",
    "Open Spotify and play a random playlist 🎧🎶",
]

# --- Helper ---
def get_username(user):
    if user.username:
        return f"@{user.username}"
    return user.first_name

def today_str():
    return datetime.utcnow().strftime("%Y-%m-%d")
# --- /start command ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.send_message(
        message.chat.id,
        "👋 Hey! I'm *Jodi Maker Bot* 💘\n\n"
        "Your group's ultimate fun companion!\n\n"
        "Here's what I can do:\n\n"
        "💘 /couple — Pick couple of the hour with a dare\n"
        "💔 /breakup @user — Send a breakup message\n"
        "🍀 /luck — Check your daily luck score\n"
        "🔍 /expose @user — Expose someone's secrets\n"
        "😌 /gettingbored — Get a fun suggestion\n\n"
        "➕ Add me to your group and let the fun begin!",
        parse_mode='Markdown'
    )
# --- /couple command ---
@bot.message_handler(commands=['couple'])
def handle_couple(message):
    print(f"COUPLE CMD from chat_id:{message.chat.id} type:{message.chat.type}")

    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "❌ This command only works in group chats!")
        return

    chat_id = message.chat.id
    current_time = time.time()

    if chat_id not in group_members:
        group_members[chat_id] = {}
    group_members[chat_id][message.from_user.id] = get_username(message.from_user)
    save_data()

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

    user_ids = list(members.keys())
    selected_ids = random.sample(user_ids, 2)
    u1_name = members[selected_ids[0]]
    u2_name = members[selected_ids[1]]

    dare = random.choice(get_dare_urls())

    couple_history[chat_id] = {
        "couple": (u1_name, u2_name),
        "dare": dare,
        "expiry": current_time + 3600
    }
    save_data()

    caption = (
        f"💘 Couple of the Hour 💘\n\n"
        f"{u1_name} ❤️ {u2_name}\n\n"
        f"{dare['text'].format(u1_name, u2_name)}\n\n"
        f"🕐 This couple refreshes in 1 hour!"
    )

    bot.send_photo(chat_id, dare['image'], caption=caption)

# --- /breakup command ---
@bot.message_handler(commands=['breakup'])
def handle_breakup(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "❌ This command only works in group chats!")
        return

    sender = get_username(message.from_user)
    chat_id = message.chat.id
    parts = message.text.split()

    if len(parts) < 2:
        bot.reply_to(message, "❌ Usage: /breakup @username")
        return

    target = parts[1]
    if not target.startswith("@"):
        target = f"@{target}"

    # Check if sender used /breakup on their own partner
    if chat_id in couple_history:
        data = couple_history[chat_id]
        u1, u2 = data['couple']
        # If sender is u1 and target is u2, or sender is u2 and target is u1
        if (sender == u1 and target == u2) or (sender == u2 and target == u1):
            del couple_history[chat_id]
            save_data()
            print(f"Couple cleared — {sender} broke up with {target}")

    breakup_image = f"{get_base()}/breakup.png"
    caption = (
        f"💔 Great decision {sender}! You deserved better!\n\n"
        f"{target} lost the 💎"
    )

    bot.send_photo(chat_id, breakup_image, caption=caption)
    
# --- /gettingbored command ---
@bot.message_handler(commands=['gettingbored'])
def handle_gettingbored(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "❌ This command only works in group chats!")
        return

    sender = get_username(message.from_user)
    suggestion = random.choice(BOREDOM_SUGGESTIONS)

    bot.send_message(
        message.chat.id,
        f"Understand {sender}, not your fault. People here are boring 😌\n\n{suggestion}"
    )
 # --- /mygroups command (owner only) ---
OWNER_ID = 1245270119

@bot.message_handler(commands=['mygroups'])
def handle_mygroups(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ This command is only for the bot owner!")
        return

    if not group_members:
        bot.reply_to(message, "No groups found!")
        return
    text = "📋 Groups where bot is active:\n\n"
    for i, (chat_id, members) in enumerate(group_members.items(), 1):
        name = group_names.get(chat_id, "Unknown Group")
        text += f"{i}. {name} — {len(members)} members\n"

    bot.send_message(message.chat.id, text, parse_mode='Markdown')   
    
# --- Expose Messages ---
EXPOSE_MESSAGES = [
    "Still sleeps with a night light 💀",
    "Laughs at their own jokes alone at 3AM 😭",
    "Googles 'how to be cool' every night 🤡",
    "Has a folder of memes they never send to anyone 🗂️",
    "Practices conversations in the mirror before texting 📱",
    "Cries watching cartoon movies 🧸😭",
    "Eats Maggi at midnight and calls it dinner 🍜",
    "Still uses the same password from 2015 🔐😬",
    "Talks to their pet like it understands everything 🐱👀",
    "Screenshots their own messages to check if they sound cool 📸",
    "Pretends to be busy but is just scrolling reels 📱😶",
    "Types and deletes messages 10 times before sending 😭",
    "Secretly watches cooking videos but can't cook anything 👨‍🍳💀",
    "Has notifications off for everyone except their crush 🔔❤️",
    "Sends 'haha' but is completely dead inside 💀",
    "Keeps refreshing apps like something new will happen 🔄😶",
    "Joins group chat, reads everything, says nothing 👀🤐",
    "Says 'I'll sleep early' and ends up online till 2AM 🌙💀",
    "Opens camera to check face… takes 10 selfies anyway 📸😏",
    "Searches meanings of words mid-conversation 🤓📲",
    "Watches tutorials at 2x speed… understands nothing 🎥💀",
    "Watches horror videos… then can't sleep alone 🌙😨",
    "Watches travel vlogs… never leaves their room ✈️🛌",
    "Acts fearless… scared to send one message 😶",
    "Gives gym advice… hasn't touched dumbbells 💪🤡",
    "Gives relationship advice… has zero experience 😭",
    "Tells people to move on… can't move on themselves 😭",
    "Acts busy but replies instantly to one specific person 📱😏",
    "Opens a door that says 'pull' and pushes anyway 🚪🤡",
    "Farts in public and acts like there's no smell at all 💀",
    "Talks to themselves and wins arguments 🧠🏆",
    "Walks faster when someone is behind them for no reason 🚶‍♂️💀",
    "Looks at phone to avoid eye contact 📱😶",
    "Thinks of fake scenarios and gets emotionally involved 🤡",
    "Checks time… forgets immediately ⏰😶",
    "Hears a sound… investigates like a detective 🕵️‍♂️💀",
    "Walks into mirror and gets scared of themselves 🪞😨",
    "Acts like a sports expert online… doesn't even know the basic rules 💀",
    "Acts like a night owl… sleeps by 11 🌙😏",
    "Thinks they're the main character… but not even a side role in reality 🎬💀",
    "Says 'I don't need anyone'… needs attention 😏",
    "Double dating and still looking for another one 💀",
    "Gets scared of their own shadow sometimes 🤡",
    "Behaves sigma on social media… chhapri in real life 🤡",
    "Acts rich online… gets heartattack even at normal price in real life 💀",
    "Acts like a movieholic… sleeps halfway through 🎬😬",
    "Still gets Pant wet while watching Bhoothnath movie 🤡",
    "Motivates everyone else… has zero motivation themselves 😶",
    "Says 'I don't watch reels'… knows every trending reel 📱🤡",
    "Tells others to stay calm… panics first 😶‍🌫️",
    "Says 'I love mornings'… hasn't seen 8AM voluntarily 🌅😭",
    "Thinks of jokes later and wishes they said it 😭",
    "Watches others do work… feels tired themselves 😭",
    "Goes to study… cleans everything except studying 📚🧹",
    "Says 'I'll just rest for 5 minutes'… wakes up 2 hours later ⏳💀",
    "Says 'I'm not hungry' then eats half the kitchen 🍜😶",
    "Says 'I'll remember this'… forgets in 2 minutes 🤡",
    "Says 'just one more video'… loses 1 hour 🎥😶",
    "Is secretly double dating and mixing up names 💀",
    "Has a 'best friend' in every group 🤡",
    "Replies late on purpose to seem busy 😏",
    "Acts single… isn't single 😭",
    "Says 'just a friend' every time 👀",
    "Has different personalities for different people 🎭",
    "Says 'I'm offline'… online somewhere else 👀",
    "Has a 'favorite person'… changes every week 🤡",
    "Says 'I hate drama'… always knows the full story 👀",
]
# --- /expose command ---
@bot.message_handler(commands=['expose'])
def handle_expose(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "❌ This command only works in group chats!")
        return

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Usage: /expose @username")
        return

    target = parts[1]
    if not target.startswith("@"):
        target = f"@{target}"

    # Prevent self-expose
    sender = get_username(message.from_user)
    if target.lower() == sender.lower():
        bot.reply_to(message, "❌ You can't expose yourself! Try someone else 😏")
        return

    chat_id = str(message.chat.id)

    # Reset if all messages used
    if chat_id not in used_expose or len(used_expose[chat_id]) >= len(EXPOSE_MESSAGES):
        used_expose[chat_id] = []

    # Pick random unused message
    all_indexes = list(range(len(EXPOSE_MESSAGES)))
    remaining = [i for i in all_indexes if i not in used_expose[chat_id]]
    chosen_index = random.choice(remaining)
    used_expose[chat_id].append(chosen_index)
    expose_msg = EXPOSE_MESSAGES[chosen_index]

    bot.send_message(
        message.chat.id,
        f"🔍 Exposed! {target}\n\n{expose_msg}"
    )
# --- /luck command ---
@bot.message_handler(commands=['luck'])
def handle_luck(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "❌ This command only works in group chats!")
        return

    user_id = str(message.from_user.id)
    username = get_username(message.from_user)
    today = today_str()

    # Check if user already has luck for today
    if user_id in luck_history and luck_history[user_id]["date"] == today:
        percent = luck_history[user_id]["percent"]
    else:
        # Generate new luck for today
        percent = random.choice([7, 14, 26, 38, 47, 55, 67, 74, 88, 96])
        luck_history[user_id] = {"percent": percent, "date": today}
        save_data()

    luck = get_luck_range(percent)
    image_url = f"{get_base()}/{luck['image']}"

    caption = (
        f"🍀 Luck Check for {username}\n\n"
        f"Your luck today: {percent}% — {luck['msg']}"
    )

    bot.send_photo(message.chat.id, image_url, caption=caption)
# --- Handle member leaving ---
@bot.message_handler(content_types=['left_chat_member'])
def handle_left_member(message):
    chat_id = message.chat.id
    left_user = message.left_chat_member
    user_id = left_user.id
    if chat_id in group_members and user_id in group_members[chat_id]:
        del group_members[chat_id][user_id]
        save_data()
        print(f"Removed {left_user.first_name} from chat {chat_id}")
        
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
    # Store group name
    if message.chat.title:
        group_names[chat_id] = message.chat.title
    save_data()

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
