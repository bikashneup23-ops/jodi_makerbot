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
    {int(k): v for k, v in data.get("members", {}).items()},
    {int(k): v for k, v in data.get("couples", {}).items()},
    data.get("luck", {}),
    {int(k): v for k, v in data.get("group_names", {}).items()},
    data.get("command_stats", {})
)
        except:
            pass
    return {}, {}, {}, {}, {}
    
def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({
            "members": {str(k): v for k, v in group_members.items()},
            "couples": {str(k): v for k, v in couple_history.items()},
            "luck": luck_history,
            "group_names": {str(k): v for k, v in group_names.items()},
            "command_stats": command_stats
        }, f)

# --- Load existing data on startup ---
group_members, couple_history, luck_history, group_names, command_stats = load_data()
print(f"Loaded {sum(len(v) for v in group_members.values())} members from file")

# --- Football Game State ---
football_games = {}

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

def get_goal_image():
    base = get_base()
    return random.choice([f"{base}/goal1.png", f"{base}/goal2.png", f"{base}/goal3.png"])

def get_save_image():
    base = get_base()
    return random.choice([f"{base}/save1.png", f"{base}/save2.png", f"{base}/save3.png"])

# --- Extract tpead.net direct link ---
def extract_tpead_link(url):
    try:
        import re
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://tpead.net/",
            "Accept-Language": "en-US,en;q=0.9"
        }
        response = requests.get(url, headers=headers, timeout=15)
        html = response.text
        print("HTML snippet:", html[html.find('norobotlink'):html.find('norobotlink')+300])

        match = re.search(r"getElementById\('norobotlink'\)\.innerHTML = '//tpead\.net/get_vide' \+ \('(.+?)'\)\.substring\(1\)\.substring\(2\)", html)
        if match:
            suffix = match.group(1)[3:]
            direct_url = "https://tpead.net/get_video" + suffix + "&stream=1"
            return direct_url

        match2 = re.search(r'id="norobotlink"[^>]*>([^<]+)<', html)
        if match2:
            path = match2.group(1).strip()
            if path.startswith("//"):
                path = "https:" + path
            return path + "&stream=1"

        return None
    except Exception as e:
        print(f"tpead extract error: {e}")
        return None

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
    "Has a playlist called 'sad hours' they use daily 🎧💔",
    "Rehearses arguments in the shower that never happen 🚿💀",
    "Types and deletes messages 10 times before sending 😭",
    "Secretly watches cooking videos but can't cook anything 👨‍🍳💀",
    "Has notifications off for everyone except their crush 🔔❤️",
    "Sends 'haha' but is completely dead inside 💀",
    "Keeps refreshing apps like something new will happen 🔄😶",
    "Joins group chat, reads everything, says nothing 👀🤐",
    "Says 'I'll sleep early' and ends up online till 2AM 🌙💀",
    "Changes bio hoping someone notices 📝😏",
    "Opens camera to check face… takes 10 selfies anyway 📸😏",
    "Searches meanings of words mid-conversation 🤓📲",
    "Watches tutorials at 2x speed… understands nothing 🎥💀",
    "Watches horror videos… then can't sleep alone 🌙😨",
    "Watches travel vlogs… never leaves their room ✈️🛌",
    "Acts fearless… scared to send one message 😶",
    "Gives gym advice… hasn't touched dumbbells 💪🤡",
    "Gives relationship advice… has zero experience 😭",
    "Tells people to move on… can't move on themselves 😭",
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
    "Has read receipts off… reads everything immediately 👀",
    "Asks 'who told you?'… they told everyone 🤡",
    "Says 'I don't care'… checks every 5 minutes 📱😶",
    "Has a 'strictly professional' contact saved with a heart 💼❤️",
    "Writes long messages… sends 'k' instead 😭",
    "Says 'I'm fine'… clearly not fine 😶‍🌫️",
    "Pretends to forget… remembers everything 🧠💀",
    "Acts confident online… shy in person 😶📱",
    "Has a crush… denies it to everyone including themselves 💀",
    "Says 'last time I'm doing this'… does it again next day 🔄😭",
    "Sends memes to avoid real conversations 🤡📱",
    "Has opinions… changes them based on who's around 😶",
    "Laughs loudly in group… texts anxiety at night 😭🌙",
    "Says 'I don't judge'… judges immediately 👀",
    "Pretends to sleep… fully awake and overthinking 🌙🧠",
    "Acts unbothered… has 47 browser tabs open about it 💀",
    "Gives advice they never follow themselves 🤡",
    "Says 'I'll be ready in 5 mins'… takes 45 minutes 😭⏳",
    "Has a 'do not disturb' on… checks phone every 2 minutes 📱😶",
    "Acts mature… sends unhinged memes at 3AM 🌙🤡",
]

# --- Helper ---
def get_username(user):
    if user.username:
        return f"@{user.username}"
    return user.first_name

def today_str():
    return datetime.utcnow().strftime("%Y-%m-%d")

# --- Owner ---
OWNER_ID = 1245270119

# --- Used expose tracker ---
used_expose = {}
# --- Horoscope cache ---
horoscope_cache = {}
# --- Stream Data ---
stream_data = {}

# --- Track command usage ---
def track_command(cmd):
    command_stats[cmd] = command_stats.get(cmd, 0) + 1
    save_data()

# ============================================================
# FLASK ROUTES
# ============================================================

@app.route('/')
def health_check():
    return "Bot is running!", 200

@app.route('/stream-url')
def get_stream_url():
    channel = request.args.get('id', '').lower()
    url = stream_data.get(channel, "")
    return {"url": url}

# ============================================================
# FOOTBALL GAME FUNCTIONS
# ============================================================

def get_game(chat_id):
    return football_games.get(chat_id)

def create_game(chat_id):
    football_games[chat_id] = {
        "state": "lobby",
        "players": [],
        "lobby_msg_id": None,
        "matches": [],
        "current_match": None,
        "tournament_winners": [],
    }
    return football_games[chat_id]

def create_match(p1, p2):
    return {
        "p1": p1,
        "p2": p2,
        "score": {p1["id"]: 0, p2["id"]: 0},
        "round": 0,
        "max_rounds": 3,
        "attacker": p1["id"],
        "choices": {},
        "state": "waiting",
        "sudden_death": False,
        "timers": {},
    }

def get_attacker(match):
    attacker_id = match["attacker"]
    if match["p1"]["id"] == attacker_id:
        return match["p1"]
    return match["p2"]

def get_defender(match):
    attacker_id = match["attacker"]
    if match["p1"]["id"] == attacker_id:
        return match["p2"]
    return match["p1"]

def send_shot_choices(match, chat_id):
    attacker = get_attacker(match)
    defender = get_defender(match)

    try:
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("⬅️ Left", callback_data=f"shot_{chat_id}_left"),
            types.InlineKeyboardButton("⬆️ Middle", callback_data=f"shot_{chat_id}_middle"),
            types.InlineKeyboardButton("➡️ Right", callback_data=f"shot_{chat_id}_right")
        )
        bot.send_message(attacker["id"], f"⚽ Your turn to SHOOT!\nChoose direction:", reply_markup=markup)
    except Exception as e:
        print(f"Could not DM attacker: {e}")
        bot.send_message(chat_id, f"⚠️ {attacker['name']} hasn't started the bot in DM! Please message the bot privately first.\nGame cancelled.")
        cancel_game(chat_id)
        return

    try:
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("⬅️ Left", callback_data=f"dive_{chat_id}_left"),
            types.InlineKeyboardButton("⬆️ Middle", callback_data=f"dive_{chat_id}_middle"),
            types.InlineKeyboardButton("➡️ Right", callback_data=f"dive_{chat_id}_right")
        )
        bot.send_message(defender["id"], f"🧤 You are the GOALKEEPER!\nChoose dive direction:", reply_markup=markup)
    except Exception as e:
        print(f"Could not DM defender: {e}")
        bot.send_message(chat_id, f"⚠️ {defender['name']} hasn't started the bot in DM! Please message the bot privately first.\nGame cancelled.")
        cancel_game(chat_id)
        return

    match["state"] = "collecting"
    timer = threading.Timer(10.0, handle_timeout, args=[chat_id])
    timer.start()
    match["timers"]["round"] = timer

def handle_timeout(chat_id):
    game = get_game(chat_id)
    if not game or not game["current_match"]:
        return
    match = game["current_match"]
    if match["state"] != "collecting":
        return

    attacker = get_attacker(match)
    defender = get_defender(match)
    directions = ["left", "middle", "right"]

    if attacker["id"] not in match["choices"]:
        match["choices"][attacker["id"]] = random.choice(directions)
        try:
            bot.send_message(attacker["id"], "⏰ Time's up! Random direction chosen for you.")
        except:
            pass

    if defender["id"] not in match["choices"]:
        match["choices"][defender["id"]] = random.choice(directions)
        try:
            bot.send_message(defender["id"], "⏰ Time's up! Random direction chosen for you.")
        except:
            pass

    process_round(chat_id)

def process_round(chat_id):
    game = get_game(chat_id)
    if not game:
        return
    match = game["current_match"]

    if "round" in match["timers"]:
        try:
            match["timers"]["round"].cancel()
        except:
            pass

    attacker = get_attacker(match)
    defender = get_defender(match)

    att_choice = match["choices"].get(attacker["id"])
    def_choice = match["choices"].get(defender["id"])

    if not att_choice or not def_choice:
        return

    if att_choice == def_choice:
        match["score"][defender["id"]] += 1
        image = get_save_image()
        msg = (
            f"🧤 SAVE! Perfect prediction!\n\n"
            f"{attacker['name']} shot {att_choice.upper()}\n"
            f"{defender['name']} dived {def_choice.upper()}\n\n"
            f"Score: {match['p1']['name']} {match['score'][match['p1']['id']]} - "
            f"{match['score'][match['p2']['id']]} {match['p2']['name']}"
        )
    else:
        match["score"][attacker["id"]] += 1
        image = get_goal_image()
        msg = (
            f"⚽ GOAL! The keeper guessed wrong!\n\n"
            f"{attacker['name']} shot {att_choice.upper()}\n"
            f"{defender['name']} dived {def_choice.upper()}\n\n"
            f"Score: {match['p1']['name']} {match['score'][match['p1']['id']]} - "
            f"{match['score'][match['p2']['id']]} {match['p2']['name']}"
        )

    bot.send_photo(chat_id, image, caption=msg)
    match["choices"] = {}
    match["attacker"] = defender["id"]
    match["round"] += 1
    check_match_end(chat_id)

def check_match_end(chat_id):
    game = get_game(chat_id)
    match = game["current_match"]
    p1 = match["p1"]
    p2 = match["p2"]
    s1 = match["score"][p1["id"]]
    s2 = match["score"][p2["id"]]

    if match["sudden_death"]:
        if s1 != s2:
            finish_match(chat_id)
        else:
            match["choices"] = {}
            bot.send_message(chat_id, "⚡ Still tied! Another sudden death round!")
            send_shot_choices(match, chat_id)
        return

    if match["round"] >= match["max_rounds"] * 2:
        if s1 == s2:
            match["sudden_death"] = True
            match["round"] = 0
            match["attacker"] = p1["id"]
            match["choices"] = {}
            bot.send_message(chat_id, f"😮 It's {s1}-{s2}! SUDDEN DEATH!\nNext goal wins! 🏆")
            send_shot_choices(match, chat_id)
        else:
            finish_match(chat_id)
    else:
        match["choices"] = {}
        round_num = (match["round"] // 2) + 1
        bot.send_message(chat_id, f"🔄 Round {round_num} — {get_attacker(match)['name']} shoots!")
        send_shot_choices(match, chat_id)

def finish_match(chat_id):
    game = get_game(chat_id)
    match = game["current_match"]
    p1 = match["p1"]
    p2 = match["p2"]
    s1 = match["score"][p1["id"]]
    s2 = match["score"][p2["id"]]

    winner = p1 if s1 > s2 else p2
    loser = p2 if s1 > s2 else p1
    match["state"] = "done"

    bot.send_message(
        chat_id,
        f"🏁 Match Over!\n\n"
        f"🏆 Winner: {winner['name']}\n"
        f"Final Score: {p1['name']} {s1} - {s2} {p2['name']}\n\n"
        f"Better luck next time {loser['name']}! 💪"
    )

    game["tournament_winners"].append(winner)
    advance_tournament(chat_id)

def advance_tournament(chat_id):
    game = get_game(chat_id)
    players = game["players"]
    winners = game["tournament_winners"]

    if len(players) == 2:
        loser = players[1] if winners[0]["id"] == players[0]["id"] else players[0]
        announce_champion(chat_id, winners[0], loser)

    elif len(players) == 3:
        if len(winners) == 1:
            played_ids = {game["matches"][0]["p1"]["id"], game["matches"][0]["p2"]["id"]}
            third = next(p for p in players if p["id"] not in played_ids)
            final_match = create_match(winners[0], third)
            game["matches"].append(final_match)
            bot.send_message(chat_id, f"🏟️ FINAL!\n{winners[0]['name']} vs {third['name']}\nGet ready! ⚽")
            time.sleep(2)
            game["current_match"] = final_match
            final_match["state"] = "collecting"
            bot.send_message(chat_id, f"🔄 Round 1 — {winners[0]['name']} shoots first!")
            send_shot_choices(final_match, chat_id)
        elif len(winners) == 2:
            final_match = game["matches"][1]
            final_ids = {final_match["p1"]["id"], final_match["p2"]["id"]}
            runner_up = next(p for p in players if p["id"] in final_ids and p["id"] != winners[1]["id"])
            announce_champion(chat_id, winners[1], runner_up)

    elif len(players) == 4:
        if len(winners) == 1:
            bot.send_message(chat_id, f"⚽ Semi-Final 2!\n{game['matches'][1]['p1']['name']} vs {game['matches'][1]['p2']['name']}\nGet ready!")
            time.sleep(2)
            start_match(chat_id, game["matches"][1]["p1"], game["matches"][1]["p2"])
        elif len(winners) == 2:
            bot.send_message(chat_id, f"🏆 GRAND FINAL!\n{winners[0]['name']} vs {winners[1]['name']}\nGet ready! ⚽")
            time.sleep(2)
            start_match(chat_id, winners[0], winners[1])
        elif len(winners) == 3:
            announce_champion(chat_id, winners[2], winners[1])

def start_match(chat_id, p1, p2):
    game = get_game(chat_id)
    match = create_match(p1, p2)
    game["current_match"] = match
    bot.send_message(chat_id, f"🔄 Round 1 — {p1['name']} shoots first!")
    send_shot_choices(match, chat_id)

def announce_champion(chat_id, champion, runner_up):
    bot.send_message(
        chat_id,
        f"🎉🏆 TOURNAMENT OVER! 🏆🎉\n\n"
        f"👑 CHAMPION: {champion['name']}\n"
        f"🥈 Runner-up: {runner_up['name']}\n\n"
        f"What a tournament! 🔥⚽"
    )
    cancel_game(chat_id)

def cancel_game(chat_id):
    if chat_id in football_games:
        del football_games[chat_id]

# ============================================================
# BOT HANDLERS
# ============================================================

@bot.message_handler(commands=['start'])
def handle_start(message):
    owner_extra = ""
    if message.from_user.id == OWNER_ID:
        owner_extra = "\n\n🛠️ *Owner Commands:*\n📢 /broadcast — Send announcement to all groups\n📋 /mygroups — List all active groups"
    bot.send_message(
        message.chat.id,
        "👋 Hey! I'm *Hourlyship Bot* 💘\n\n"
        "Your group's ultimate fun companion!\n\n"
        "Here's what I can do:\n\n"
        "🎬 /stream — Match live streaming\n"
        "💘 /couple — Pick couple of the hour with a dare\n"
        "💔 /breakup @user — Send a breakup message\n"
        "🍀 /luck — Check your daily luck score\n"
        "🔮 /horoscope — Get your zodiac horoscope\n"
        "🔍 /expose @user — Expose someone's secrets\n"
        "😌 /gettingbored — Get a fun suggestion\n"
        f"⚽ /football — Start a penalty shootout tournament{owner_extra}\n\n"
        "➕ Add me to your group and let the fun begin!",
        parse_mode='Markdown'
    )
    if message.chat.type == 'private':
        handle_stream(message)

@bot.message_handler(commands=['couple'])
def handle_couple(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "❌ This command only works in group chats!")
        return
    track_command("couple")

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
        bot.reply_to(message, "👥 I need at least 2 active members!\nHave others send a message in the group first, then try again.")
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

@bot.message_handler(commands=['breakup'])
def handle_breakup(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "❌ This command only works in group chats!")
        return
    track_command("breakup")

    sender = get_username(message.from_user)
    chat_id = message.chat.id
    parts = message.text.split()

    if len(parts) < 2:
        bot.reply_to(message, "❌ Usage: /breakup @username")
        return

    target = parts[1]
    if not target.startswith("@"):
        target = f"@{target}"

    if chat_id in couple_history:
        data = couple_history[chat_id]
        u1, u2 = data['couple']
        if (sender == u1 and target == u2) or (sender == u2 and target == u1):
            del couple_history[chat_id]
            save_data()

    breakup_image = f"{get_base()}/breakup.png"
    caption = (
        f"💔 Great decision {sender}! You deserved better!\n\n"
        f"{target} lost the 💎"
    )
    bot.send_photo(chat_id, breakup_image, caption=caption)

@bot.message_handler(commands=['gettingbored'])
def handle_gettingbored(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "❌ This command only works in group chats!")
        return
    track_command("gettingbored")

    sender = get_username(message.from_user)
    suggestion = random.choice(BOREDOM_SUGGESTIONS)
    bot.send_message(message.chat.id, f"Understand {sender}, not your fault. People here are boring 😌\n\n{suggestion}")

@bot.message_handler(commands=['horoscope'])
def handle_horoscope(message):
    track_command("horoscope")

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

    bot.send_message(
        message.chat.id,
        f"🔮 {get_username(message.from_user)}, choose your zodiac sign:",
        reply_markup=markup
    )

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
        member_list = ", ".join(members.values()) if members else "No members"
        text += f"{i}. {name} — {len(members)} members\n   👥 {member_list}\n\n"

    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            bot.send_message(message.chat.id, text[i:i+4000])
    else:
        bot.send_message(message.chat.id, text)

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

    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['broadcast'])
def handle_broadcast(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ This command is only for the bot owner!")
        return

    if not group_members:
        bot.reply_to(message, "❌ No active groups found!")
        return

    parts = message.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "❌ Usage: /broadcast your message here")
        return

    broadcast_text = f"📢 Announcement:\n\n{parts[1].strip()}"

    success = 0
    failed = 0
    for chat_id in list(group_members.keys()):
        try:
            bot.send_message(chat_id, broadcast_text)
            success += 1
        except Exception as e:
            print(f"Failed to send to {chat_id}: {e}")
            failed += 1

    bot.reply_to(message, f"✅ Broadcast done!\n\n📤 Sent: {success} groups\n❌ Failed: {failed} groups")

@bot.message_handler(commands=['setstream'])
def handle_setstream(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Owner only!")
        return
    parts = message.text.split(None, 2)
    if len(parts) < 3:
        bot.reply_to(message, "❌ Usage: /setstream <id> <url>\nExample: /setstream fifa1 https://...")
        return
    channel_id = parts[1].lower()
    stream_data[channel_id] = parts[2].strip()
    bot.reply_to(message, f"✅ Stream updated!\n\n🔗 ID: `{channel_id}`\n📺 URL: {stream_data[channel_id]}", parse_mode='Markdown')

@bot.message_handler(commands=['clearstream'])
def handle_clearstream(message):
    if message.from_user.id != OWNER_ID:
        bot.reply_to(message, "❌ Owner only!")
        return
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        bot.reply_to(message, "❌ Usage: /clearstream <id>\nExample: /clearstream fifa1")
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

@bot.message_handler(commands=['stream'])
def handle_stream(message):
    track_command("stream")

    if not stream_data:
        bot.reply_to(message, "⚠️ No streams are currently active. Check back later!")
        return

    STREAM_PAGE = "https://hourlyship.pages.dev"
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
            print(f"Could not DM {message.from_user.id}: {e}")
            bot.reply_to(
                message,
                f"⚠️ {get_username(message.from_user)}, I couldn't send you a DM!\n"
                f"Please start the bot first 👉 @{bot.get_me().username}\n"
                f"Then send /stream again."
            )
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
    track_command("luck")

    user_id = str(message.from_user.id)
    username = get_username(message.from_user)
    today = today_str()

    if user_id in luck_history and luck_history[user_id]["date"] == today:
        percent = luck_history[user_id]["percent"]
    else:
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

@bot.message_handler(commands=['expose'])
def handle_expose(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "❌ This command only works in group chats!")
        return
    track_command("expose")

    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Usage: /expose @username")
        return

    target = parts[1]
    if not target.startswith("@"):
        target = f"@{target}"

    sender = get_username(message.from_user)
    if target.lower() == sender.lower():
        bot.reply_to(message, "❌ You can't expose yourself! Try someone else 😏")
        return

    chat_id = str(message.chat.id)
    if chat_id not in used_expose or len(used_expose[chat_id]) >= len(EXPOSE_MESSAGES):
        used_expose[chat_id] = []

    all_indexes = list(range(len(EXPOSE_MESSAGES)))
    remaining = [i for i in all_indexes if i not in used_expose[chat_id]]
    chosen_index = random.choice(remaining)
    used_expose[chat_id].append(chosen_index)
    expose_msg = EXPOSE_MESSAGES[chosen_index]

    bot.send_message(message.chat.id, f"🔍 Exposed! {target}\n\n{expose_msg}")

@bot.message_handler(commands=['football'])
def handle_football(message):
    if message.chat.type not in ['group', 'supergroup']:
        bot.reply_to(message, "❌ This command only works in group chats!")
        return
    track_command("football")

    chat_id = message.chat.id

    if chat_id in football_games:
        bot.reply_to(message, "⚽ A game is already in progress!")
        return

    game = create_game(chat_id)

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⚽ Join Match", callback_data=f"football_join_{chat_id}"))

    msg = bot.send_message(
        chat_id,
        "🏟️ Football Penalty Tournament!\n\n"
        "Players joined: 0/4\n\n"
        "Click to join! Min 2, Max 4 players.\n"
        "⏳ Lobby closes in 20 seconds!",
        reply_markup=markup
    )

    game["lobby_msg_id"] = msg.message_id

    timer = threading.Timer(20.0, lobby_timeout, args=[chat_id])
    timer.start()
    game["lobby_timer"] = timer

def lobby_timeout(chat_id):
    game = get_game(chat_id)
    if not game or game["state"] != "lobby":
        return

    players = game["players"]
    if len(players) < 2:
        bot.send_message(chat_id, "❌ Not enough players joined! Match cancelled.\nTry /football again.")
        cancel_game(chat_id)
    else:
        start_tournament(chat_id)

def start_tournament(chat_id):
    game = get_game(chat_id)
    players = game["players"]

    if "lobby_timer" in game:
        try:
            game["lobby_timer"].cancel()
        except:
            pass

    random.shuffle(players)
    n = len(players)

    bot.send_message(
        chat_id,
        f"🏆 Tournament starting with {n} players!\n\n"
        + "\n".join([f"{i+1}. {p['name']}" for i, p in enumerate(players)])
    )
    time.sleep(2)

    if n == 2:
        game["state"] = "final"
        match = create_match(players[0], players[1])
        game["matches"].append(match)
        bot.send_message(chat_id, f"⚽ FINAL!\n{players[0]['name']} vs {players[1]['name']}\nGet ready!")
        time.sleep(2)
        start_match(chat_id, players[0], players[1])

    elif n == 3:
        game["state"] = "semifinal"
        match = create_match(players[0], players[1])
        game["matches"].append(match)
        bot.send_message(chat_id, f"⚽ Semi-Final!\n{players[0]['name']} vs {players[1]['name']}\nGet ready!")
        time.sleep(2)
        start_match(chat_id, players[0], players[1])

    elif n == 4:
        game["state"] = "semifinal"
        match1 = create_match(players[0], players[1])
        match2 = create_match(players[2], players[3])
        game["matches"].extend([match1, match2])
        bot.send_message(chat_id, f"⚽ Semi-Final 1!\n{players[0]['name']} vs {players[1]['name']}\nGet ready!")
        time.sleep(2)
        start_match(chat_id, players[0], players[1])

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    data = call.data

    if data.startswith("football_join_"):
        chat_id = int(data.split("_")[2])
        game = get_game(chat_id)

        if not game or game["state"] != "lobby":
            bot.answer_callback_query(call.id, "❌ No active lobby!")
            return

        user_id = call.from_user.id
        username = get_username(call.from_user)

        if any(p["id"] == user_id for p in game["players"]):
            bot.answer_callback_query(call.id, "You already joined!")
            return

        if len(game["players"]) >= 4:
            bot.answer_callback_query(call.id, "Lobby is full!")
            return

        game["players"].append({"id": user_id, "name": username})
        count = len(game["players"])
        bot.answer_callback_query(call.id, f"✅ Joined! ({count}/4)")

        player_list = "\n".join([f"✅ {p['name']}" for p in game["players"]])
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("⚽ Join Match", callback_data=f"football_join_{chat_id}"))

        try:
            bot.edit_message_text(
                f"🏟️ Football Penalty Tournament!\n\n"
                f"Players joined: {count}/4\n\n"
                f"{player_list}\n\n"
                f"{'⏳ Waiting for more players...' if count < 4 else '🚀 Starting now!'}",
                chat_id, game["lobby_msg_id"],
                reply_markup=markup if count < 4 else None
            )
        except:
            pass

        if count == 4:
            if "lobby_timer" in game:
                try:
                    game["lobby_timer"].cancel()
                except:
                    pass
            time.sleep(1)
            start_tournament(chat_id)

    elif data.startswith("shot_"):
        parts = data.split("_")
        chat_id = int(parts[1])
        direction = parts[2]

        game = get_game(chat_id)
        if not game or not game["current_match"]:
            bot.answer_callback_query(call.id, "No active match!")
            return

        match = game["current_match"]
        attacker = get_attacker(match)

        if call.from_user.id != attacker["id"]:
            bot.answer_callback_query(call.id, "❌ You're not the attacker!")
            return

        if attacker["id"] in match["choices"]:
            bot.answer_callback_query(call.id, "Already chosen!")
            return

        match["choices"][attacker["id"]] = direction
        bot.answer_callback_query(call.id, f"✅ Shot {direction}!")

        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            bot.send_message(call.from_user.id, f"✅ You shot {direction.upper()}! Waiting for goalkeeper...")
        except:
            pass

        defender = get_defender(match)
        if defender["id"] in match["choices"]:
            process_round(chat_id)

    elif data.startswith("horo_"):
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
                print(f"Horoscope raw response: {data_json}")
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

                horoscope_cache[cache_key] = {
                    "sign": sign,
                    "date": today,
                    "text": horoscope_text
                }
            except Exception as e:
                print(f"Horoscope API error: {e}")
                bot.send_message(call.message.chat.id, "❌ Could not fetch horoscope right now. Try again later!")
                return

        username = get_username(call.from_user)
        sign_emojis = {
            "aries": "♈", "taurus": "♉", "gemini": "♊", "cancer": "♋",
            "leo": "♌", "virgo": "♍", "libra": "♎", "scorpio": "♏",
            "sagittarius": "♐", "capricorn": "♑", "aquarius": "♒", "pisces": "♓"
        }
        emoji = sign_emojis.get(sign, "🔮")

        bot.send_message(
            call.message.chat.id,
            f"{emoji} {sign.capitalize()} Horoscope for {username}\n\n{horoscope_text}"
        )

        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except:
            pass

    elif data.startswith("dive_"):
        parts = data.split("_")
        chat_id = int(parts[1])
        direction = parts[2]

        game = get_game(chat_id)
        if not game or not game["current_match"]:
            bot.answer_callback_query(call.id, "No active match!")
            return

        match = game["current_match"]
        defender = get_defender(match)

        if call.from_user.id != defender["id"]:
            bot.answer_callback_query(call.id, "❌ You're not the goalkeeper!")
            return

        if defender["id"] in match["choices"]:
            bot.answer_callback_query(call.id, "Already chosen!")
            return

        match["choices"][defender["id"]] = direction
        bot.answer_callback_query(call.id, f"✅ Dived {direction}!")

        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            bot.send_message(call.from_user.id, f"✅ You dived {direction.upper()}! Waiting for attacker...")
        except:
            pass

        attacker = get_attacker(match)
        if attacker["id"] in match["choices"]:
            process_round(chat_id)

@bot.message_handler(func=lambda message: message.chat.type == 'private' and
                     message.text and
                     ('streamtape' in message.text.lower() or 'tpead' in message.text.lower()))
def handle_tpead_link(message):
    url = message.text.strip()
    processing_msg = bot.reply_to(message, "⏳ Processing video... Please wait.")

    def process_and_send():
        direct_url = extract_tpead_link(url)
        if not direct_url:
            bot.edit_message_text(
                "❌ Could not extract video. The link may have expired or is invalid.",
                message.chat.id,
                processing_msg.message_id
            )
            return
        try:
            bot.delete_message(message.chat.id, processing_msg.message_id)
            bot.send_message(
                message.chat.id,
                f"🎬 *Video Ready!*\n\n"
                f"`{direct_url}`\n\n"
                f"📌 *How to play:*\n"
                f"*VLC:* Media → Open Network Stream → paste link\n"
                f"*NS Player:* Add URL → paste link\n"
                f"*MX Player:* Stream → paste link\n\n"
                f"⚠️ *Link expires in ~24 hours*",
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"Error sending URL: {e}")
            bot.send_message(message.chat.id, "❌ Failed to process link. Try again.")

    threading.Thread(target=process_and_send, daemon=True).start()

@bot.message_handler(content_types=['left_chat_member'])
def handle_left_member(message):
    chat_id = message.chat.id
    left_user = message.left_chat_member
    user_id = left_user.id
    if chat_id in group_members and user_id in group_members[chat_id]:
        del group_members[chat_id][user_id]
        save_data()

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
    if message.chat.title:
        group_names[chat_id] = message.chat.title
    save_data()

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_str = request.get_data(as_text=True)
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return 'ok', 200

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

if __name__ == "__main__":
    print(f"TOKEN loaded: {bool(TOKEN)}")
    print(f"RENDER_URL: {RENDER_URL}")
    set_webhook()
    print("Bot is starting in webhook mode...")
    app.run(host="0.0.0.0", port=PORT)
