import os
import telebot
from telebot import types
import sqlite3
from flask import Flask
import threading
import random
import time

# ==================== FLASK ====================
app = Flask(__name__)

@app.route('/')
def health():
    return "Bot is running"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

threading.Thread(target=run_flask, daemon=True).start()

# ==================== КОНФИГ ====================
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 8521250777
ACCEPT_TIMEOUT = 60
MAPS = ["Breeze", "Rust", "Province", "Sakura", "Sandstone"]

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# ==================== БАЗА ДАННЫХ ====================
DB = "faceit.db"

def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            game_id TEXT,
            device TEXT,
            elo INTEGER DEFAULT 1000,
            coins INTEGER DEFAULT 100,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            kills INTEGER DEFAULT 0,
            deaths INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            registered INTEGER DEFAULT 0,
            is_bot INTEGER DEFAULT 0
        )
    ''')
    cur.execute("INSERT OR IGNORE INTO players (user_id, username, registered, is_admin) VALUES (?, 'Admin', 1, 1)", (ADMIN_ID,))
    # Создаём ботов с уникальными ID
    for i in range(1, 21):
        bot_id = 1000000000 + i
        cur.execute("INSERT OR IGNORE INTO players (user_id, username, game_id, device, registered, is_bot, elo) VALUES (?, ?, ?, ?, 1, 1, 1000)", 
                   (bot_id, f"Bot_{i}", str(500000000 + i), "PC" if i % 2 == 0 else "MOBILE"))
    conn.commit()
    conn.close()

def register_user(user_id, username, game_id, device):
    conn = sqlite3.connect(DB)
    conn.execute("INSERT OR REPLACE INTO players (user_id, username, game_id, device, registered, coins, elo) VALUES (?,?,?,?,1,100,1000)", (user_id, username, game_id, device))
    conn.commit()
    conn.close()

def get_player(user_id):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row

def is_registered(user_id):
    p = get_player(user_id)
    return p is not None and p[12] == 1

def is_admin(user_id):
    p = get_player(user_id)
    return p is not None and p[11] == 1

def is_bot(user_id):
    p = get_player(user_id)
    return p is not None and p[13] == 1

def get_bots():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT user_id, username FROM players WHERE is_bot=1")
    bots = cur.fetchall()
    conn.close()
    return bots

def update_player_stats(user_id, kills, deaths, assists, won, coins_earned):
    p = get_player(user_id)
    if not p:
        return
    new_elo = p[4]
    if won:
        if kills >= 11:
            new_elo += 17
        else:
            new_elo += 17
        wins = p[6] + 1
        losses = p[7]
    else:
        if kills >= 11:
            new_elo -= 15
        else:
            new_elo -= 25
        wins = p[6]
        losses = p[7] + 1
    
    conn = sqlite3.connect(DB)
    conn.execute("UPDATE players SET elo=?, wins=?, losses=?, kills=kills+?, deaths=deaths+?, assists=assists+?, coins=coins+? WHERE user_id=?", 
                (new_elo, wins, losses, kills, deaths, assists, coins_earned, user_id))
    conn.commit()
    conn.close()

# ==================== ГЛАВНОЕ МЕНЮ ====================
def main_menu(uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        types.InlineKeyboardButton("🎮 Найти матч", callback_data="find"),
        types.InlineKeyboardButton("🏆 Топ", callback_data="top"),
        types.InlineKeyboardButton("🛒 Магазин", callback_data="shop"),
        types.InlineKeyboardButton("🎒 Инвентарь", callback_data="inv")
    )
    if is_admin(uid):
        kb.add(types.InlineKeyboardButton("🤖 Добавить ботов", callback_data="add_bots_admin"))
    return kb

@bot.message_handler(commands=['start'])
def cmd_start(msg):
    uid = msg.from_user.id
    if is_registered(uid):
        bot.send_message(uid, "⚡ ACTUAL FACEIT", reply_markup=main_menu(uid))
        return
    user_flow[uid] = {"state": "nick"}
    bot.send_message(uid, "👋 Добро пожаловать!\n\n<b>Шаг 1:</b> Введи свой никнейм (2-20 символов):", parse_mode="HTML")

# ==================== РЕГИСТРАЦИЯ ====================
user_flow = {}

@bot.message_handler(func=lambda m: user_flow.get(m.from_user.id, {}).get("state") == "nick")
def reg_nick(msg):
    uid = msg.from_user.id
    nick = msg.text.strip()
    if not (2 <= len(nick) <= 20):
        bot.send_message(uid, "❌ Никнейм 2-20 символов")
        return
    user_flow[uid] = {"state": "id", "nick": nick}
    bot.send_message(uid, "<b>Шаг 2:</b> Введи игровой ID (цифры):", parse_mode="HTML")

@bot.message_handler(func=lambda m: user_flow.get(m.from_user.id, {}).get("state") == "id")
def reg_id(msg):
    uid = msg.from_user.id
    game_id = msg.text.strip()
    if not game_id.isdigit():
        bot.send_message(uid, "❌ Только цифры")
        return
    user_flow[uid]["game_id"] = game_id
    user_flow[uid]["state"] = "device"
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row("MOBILE", "PC")
    bot.send_message(uid, "<b>Шаг 3:</b> Выбери устройство:", reply_markup=kb, parse_mode="HTML")

@bot.message_handler(func=lambda m: user_flow.get(m.from_user.id, {}).get("state") == "device")
def reg_device(msg):
    uid = msg.from_user.id
    device = msg.text.strip()
    if device not in ("MOBILE", "PC"):
        bot.send_message(uid, "❌ Выбери MOBILE или PC")
        return
    data = user_flow.pop(uid)
    register_user(uid, data["nick"], data["game_id"], device)
    kb_remove = types.ReplyKeyboardRemove()
    bot.send_message(uid, f"✅ Регистрация завершена!\n\nНик: {data['nick']}\nGame ID: {data['game_id']}\nDevice: {device}", reply_markup=kb_remove, parse_mode="HTML")
    bot.send_message(uid, "⚡ ACTUAL FACEIT", reply_markup=main_menu(uid))

# ==================== ПРОФИЛЬ ====================
def get_profile_text(uid):
    p = get_player(uid)
    if not p:
        return "❌ Ошибка"
    games = p[6] + p[7]
    winrate = round(p[6] / games * 100, 1) if games > 0 else 0
    kd = round(p[8] / p[9], 2) if p[9] > 0 else p[8]
    return (f"👤 <b>{p[1]}</b>\n🆔 ID: {p[0]}\n🎮 Game ID: {p[2]}\n📱 Device: {p[3]}\n📊 ELO: {p[4]}\n💰 Монет: {p[5]}\n\n🏆 Побед: {p[6]}\n❌ Поражений: {p[7]}\n🔫 Убийств: {p[8]}\n💀 Смертей: {p[9]}\n🤝 Ассистов: {p[10]}\n📊 K/D: {kd}\n📈 Винрейт: {winrate}%")

@bot.callback_query_handler(func=lambda c: c.data == "profile")
def cb_profile(c):
    text = get_profile_text(c.from_user.id)
    bot.edit_message_text(text, c.message.chat.id, c.message.message_id, parse_mode="HTML")
    bot.answer_callback_query(c.id)

# ==================== ЛОББИ ====================
active_lobbies = {}
user_lobby = {}

@bot.callback_query_handler(func=lambda c: c.data == "find")
def cb_find(c):
    uid = c.from_user.id
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🎮 Default", callback_data="lobby_default"),
        types.InlineKeyboardButton("⭐ Quals", callback_data="lobby_quals"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="back")
    )
    bot.edit_message_text("🎮 Выбери лигу:", c.message.chat.id, c.message.message_id, reply_markup=kb)
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data == "back")
def cb_back(c):
    uid = c.from_user.id
    bot.edit_message_text("⚡ ACTUAL FACEIT", c.message.chat.id, c.message.message_id, reply_markup=main_menu(uid))
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("lobby_"))
def cb_lobby(c):
    league = c.data.split("_")[1]
    text = f"🎮 <b>ЛОББИ {league.upper()}</b>\n\n"
    kb = types.InlineKeyboardMarkup(row_width=5)
    for slot in range(1, 6):
        mobile_id = f"{league}_mobile_{slot}"
        pc_id = f"{league}_pc_{slot}"
        mobile_count = len(active_lobbies.get(mobile_id, {}).get("players", []))
        pc_count = len(active_lobbies.get(pc_id, {}).get("players", []))
        text += f"Лобби #{slot}: Mobile({mobile_count}/10) | PC({pc_count}/10)\n"
    for slot in range(1, 6):
        mobile_count = len(active_lobbies.get(f"{league}_mobile_{slot}", {}).get("players", []))
        pc_count = len(active_lobbies.get(f"{league}_pc_{slot}", {}).get("players", []))
        kb.add(types.InlineKeyboardButton(f"M{slot}({mobile_count})", callback_data=f"join_{league}_mobile_{slot}"),
               types.InlineKeyboardButton(f"P{slot}({pc_count})", callback_data=f"join_{league}_pc_{slot}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="find"))
    bot.edit_message_text(text, c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("join_"))
def cb_join(c):
    _, league, device, slot = c.data.split("_")
    slot = int(slot)
    uid = c.from_user.id
    lobby_id = f"{league}_{device}_{slot}"
    old = user_lobby.get(uid)
    if old and old in active_lobbies:
        if uid in active_lobbies[old]["players"]:
            active_lobbies[old]["players"].remove(uid)
            if len(active_lobbies[old]["players"]) == 0:
                del active_lobbies[old]
    if lobby_id not in active_lobbies:
        active_lobbies[lobby_id] = {"players": [], "league": league, "device": device, "slot": slot, "status": "waiting"}
    lobby = active_lobbies[lobby_id]
    if lobby["status"] != "waiting":
        bot.answer_callback_query(c.id, "❌ Лобби уже в игре!", show_alert=True)
        return
    if len(lobby["players"]) >= 10:
        bot.answer_callback_query(c.id, "❌ Лобби полное!", show_alert=True)
        return
    lobby["players"].append(uid)
    user_lobby[uid] = lobby_id
    bot.answer_callback_query(c.id, f"✅ Вы вошли в лобби {slot}!")
    if len(lobby["players"]) >= 10:
        start_accept_phase(lobby_id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("leave_"))
def cb_leave(c):
    lobby_id = c.data.split("_", 1)[1]
    uid = c.from_user.id
    if lobby_id in active_lobbies and uid in active_lobbies[lobby_id]["players"]:
        active_lobbies[lobby_id]["players"].remove(uid)
        user_lobby.pop(uid, None)
        if len(active_lobbies[lobby_id]["players"]) == 0:
            del active_lobbies[lobby_id]
    bot.answer_callback_query(c.id, "✅ Вы вышли из лобби")
    league = lobby_id.split("_")[0]
    cb_lobby(c)

# ==================== ПРИНЯТИЕ МАТЧА (БОТЫ ПРИНИМАЮТ АВТОМАТИЧЕСКИ) ====================
def start_accept_phase(lobby_id):
    lobby = active_lobbies.get(lobby_id)
    if not lobby or lobby["status"] != "waiting":
        return
    lobby["status"] = "accept"
    lobby["ready"] = set()
    lobby["accept_timers"] = {}
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Принять матч", callback_data=f"accept_{lobby_id}"))
    kb.add(types.InlineKeyboardButton("🚪 Выйти", callback_data=f"leave_{lobby_id}"))
    for uid in lobby["players"]:
        if is_bot(uid):
            lobby["ready"].add(uid)
            continue
        try:
            bot.send_message(uid, f"⚔️ <b>МАТЧ НАЙДЕН!</b>\n\n⏳ У вас есть {ACCEPT_TIMEOUT} секунд!", reply_markup=kb, parse_mode="HTML")
        except:
            pass
        start_accept_timer(lobby_id, uid)
    check_all_ready(lobby_id)

def start_accept_timer(lobby_id, uid):
    t = threading.Timer(ACCEPT_TIMEOUT, accept_timeout, [lobby_id, uid])
    t.start()
    active_lobbies[lobby_id]["accept_timers"][uid] = t

def accept_timeout(lobby_id, uid):
    lobby = active_lobbies.get(lobby_id)
    if not lobby or lobby["status"] != "accept":
        return
    if uid in lobby["ready"]:
        return
    if uid in lobby["players"]:
        lobby["players"].remove(uid)
    user_lobby.pop(uid, None)
    if uid in lobby["accept_timers"]:
        lobby["accept_timers"][uid].cancel()
        del lobby["accept_timers"][uid]
    try:
        bot.send_message(uid, "⚠️ Вы не приняли матч! Вы вышли из лобби.", parse_mode="HTML")
    except:
        pass
    if len(lobby["players"]) < 10:
        lobby["status"] = "waiting"
        for member_uid in lobby["players"]:
            try:
                bot.send_message(member_uid, "❌ Игрок не принял матч. Поиск возобновлён...", parse_mode="HTML")
            except:
                pass

def check_all_ready(lobby_id):
    lobby = active_lobbies.get(lobby_id)
    if not lobby or lobby["status"] != "accept":
        return
    if len(lobby["ready"]) == len(lobby["players"]):
        for member_uid in lobby["players"]:
            try:
                bot.send_message(member_uid, "✅ Все приняли матч! Начинаем выбор карты...", parse_mode="HTML")
            except:
                pass
        start_veto(lobby_id)
    else:
        threading.Timer(1.0, check_all_ready, [lobby_id]).start()

@bot.callback_query_handler(func=lambda c: c.data.startswith("accept_"))
def cb_accept_match(c):
    lobby_id = c.data.split("_", 1)[1]
    uid = c.from_user.id
    lobby = active_lobbies.get(lobby_id)
    if not lobby or lobby["status"] != "accept":
        bot.answer_callback_query(c.id, "❌ Матч не найден")
        return
    if uid not in lobby["players"]:
        bot.answer_callback_query(c.id, "❌ Вы не в этом лобби")
        return
    lobby["ready"].add(uid)
    if uid in lobby["accept_timers"]:
        lobby["accept_timers"][uid].cancel()
        del lobby["accept_timers"][uid]
    bot.answer_callback_query(c.id, "✅ Вы приняли матч!")

# ==================== ВЕТО КАРТ (БОТЫ БАНЯТ АВТОМАТИЧЕСКИ) ====================
def start_veto(lobby_id):
    lobby = active_lobbies.get(lobby_id)
    if not lobby or lobby["status"] != "accept":
        return
    lobby["status"] = "veto"
    lobby["bans"] = []
    lobby["map_pool"] = MAPS.copy()
    lobby["ban_count"] = 0
    lobby["veto_turn"] = "ct"
    players = lobby["players"].copy()
    random.shuffle(players)
    lobby["team_ct"] = players[:5]
    lobby["team_t"] = players[5:]
    lobby["captain_ct"] = lobby["team_ct"][0]
    lobby["captain_t"] = lobby["team_t"][0]
    for uid in lobby["team_ct"]:
        try:
            bot.send_message(uid, f"🟦 Вы в команде CT! Капитан: {get_player(lobby['captain_ct'])[1]}", parse_mode="HTML")
        except:
            pass
    for uid in lobby["team_t"]:
        try:
            bot.send_message(uid, f"🟧 Вы в команде T! Капитан: {get_player(lobby['captain_t'])[1]}", parse_mode="HTML")
        except:
            pass
    send_veto_message(lobby_id)

def send_veto_message(lobby_id):
    lobby = active_lobbies.get(lobby_id)
    if not lobby or lobby["status"] != "veto":
        return
    turn = lobby["veto_turn"]
    captain = lobby["captain_ct"] if turn == "ct" else lobby["captain_t"]
    captain_name = get_player(captain)[1] if get_player(captain) else str(captain)
    text = f"🗺 ВЫБОР КАРТЫ\n\nБан {lobby['ban_count']+1}/4\nХод: {'CT' if turn=='ct' else 'T'}\nКапитан: {captain_name}\n\nДоступные карты:\n" + "\n".join([f"{i+1}. {m}" for i, m in enumerate(lobby["map_pool"])])
    kb = types.InlineKeyboardMarkup(row_width=2)
    for map_name in lobby["map_pool"]:
        kb.add(types.InlineKeyboardButton(f"❌ Забанить {map_name}", callback_data=f"ban_{lobby_id}_{map_name}"))
    for uid in lobby["players"]:
        try:
            if uid == captain and not is_bot(uid):
                bot.send_message(uid, text, reply_markup=kb, parse_mode="HTML")
            else:
                bot.send_message(uid, text, parse_mode="HTML")
        except:
            pass
    if is_bot(captain):
        threading.Timer(2.0, bot_ban, [lobby_id]).start()

def bot_ban(lobby_id):
    lobby = active_lobbies.get(lobby_id)
    if not lobby or lobby["status"] != "veto" or not lobby["map_pool"]:
        return
    map_name = random.choice(lobby["map_pool"])
    do_ban(lobby_id, map_name)

@bot.callback_query_handler(func=lambda c: c.data.startswith("ban_"))
def cb_ban(c):
    _, lobby_id, map_name = c.data.split("_", 2)
    uid = c.from_user.id
    lobby = active_lobbies.get(lobby_id)
    if not lobby or lobby["status"] != "veto":
        bot.answer_callback_query(c.id, "❌ Вето недоступно")
        return
    turn = lobby["veto_turn"]
    captain = lobby["captain_ct"] if turn == "ct" else lobby["captain_t"]
    if uid != captain:
        bot.answer_callback_query(c.id, "❌ Сейчас не ваш ход!")
        return
    if map_name not in lobby["map_pool"]:
        bot.answer_callback_query(c.id, "❌ Карта уже забанена")
        return
    do_ban(lobby_id, map_name)
    bot.answer_callback_query(c.id, f"✅ Карта {map_name} забанена!")

def do_ban(lobby_id, map_name):
    lobby = active_lobbies.get(lobby_id)
    if not lobby:
        return
    turn = lobby["veto_turn"]
    lobby["map_pool"].remove(map_name)
    lobby["bans"].append({"map": map_name, "by": turn})
    lobby["ban_count"] += 1
    for uid in lobby["players"]:
        try:
            bot.send_message(uid, f"🚫 {'CT' if turn=='ct' else 'T'} забанил {map_name}", parse_mode="HTML")
        except:
            pass
    lobby["veto_turn"] = "t" if turn == "ct" else "ct"
    if lobby["ban_count"] >= 4 and len(lobby["map_pool"]) == 1:
        final_map = lobby["map_pool"][0]
        for uid in lobby["players"]:
            try:
                bot.send_message(uid, f"✅ Финальная карта: {final_map}", parse_mode="HTML")
            except:
                pass
        start_match(lobby_id, final_map)
    else:
        send_veto_message(lobby_id)

# ==================== НАЧАЛО МАТЧА И РЕГИСТРАЦИЯ РЕЗУЛЬТАТОВ ====================
match_registration = {}

def start_match(lobby_id, map_name):
    lobby = active_lobbies.get(lobby_id)
    if not lobby:
        return
    lobby["status"] = "active"
    lobby["map_name"] = map_name
    lobby["match_start_time"] = time.time()
    text = f"⚔️ МАТЧ НАЧАЛСЯ!\n\n🗺 Карта: {map_name}\n🏆 Лига: {lobby['league'].upper()}\n\n🟦 КОМАНДА CT\n" + "\n".join([f"{i+1}. {get_player(uid)[1]}" for i, uid in enumerate(lobby["team_ct"])]) + "\n\n🟧 КОМАНДА T\n" + "\n".join([f"{i+1}. {get_player(uid)[1]}" for i, uid in enumerate(lobby["team_t"])]) + "\n\n📸 После матча админ может зарегистрировать результат!"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📸 Зарегистрировать результат", callback_data=f"reg_result_{lobby_id}"))
    for uid in lobby["players"]:
        try:
            bot.send_message(uid, text, reply_markup=kb, parse_mode="HTML")
        except:
            pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("reg_result_"))
def cb_reg_result(c):
    lobby_id = c.data.split("_", 2)[2]
    uid = c.from_user.id
    lobby = active_lobbies.get(lobby_id)
    if not lobby or lobby["status"] != "active":
        bot.answer_callback_query(c.id, "❌ Матч не найден")
        return
    if not is_admin(uid):
        bot.answer_callback_query(c.id, "❌ Только администратор")
        return
    bot.answer_callback_query(c.id)
    match_registration[uid] = {"lobby_id": lobby_id, "step": "score"}
    bot.send_message(uid, "📝 Введите счёт матча (например, 13:11)", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.from_user.id in match_registration and match_registration[m.from_user.id].get("step") == "score")
def handle_match_score(msg):
    uid = msg.from_user.id
    data = match_registration[uid]
    lobby = active_lobbies.get(data["lobby_id"])
    if not lobby:
        bot.send_message(uid, "❌ Матч не найден")
        del match_registration[uid]
        return
    try:
        parts = msg.text.strip().split(":")
        score_w = int(parts[0])
        score_l = int(parts[1])
        data["score_w"] = score_w
        data["score_l"] = score_l
        if score_w > score_l:
            data["winner"] = "ct" if score_w > score_l else "t"
            data["step"] = "stats_ct"
            bot.send_message(uid, f"✅ Счёт {score_w}:{score_l}\n\nВведите статистику CT (5 игроков, формат: ID K A D, по одному на строку):")
        else:
            data["step"] = "winner"
            bot.send_message(uid, "Счёт равный! Кто победил? Напишите CT или T")
    except:
        bot.send_message(uid, "❌ Неверный формат! Используйте 13:11")

@bot.message_handler(func=lambda m: m.from_user.id in match_registration and match_registration[m.from_user.id].get("step") == "winner")
def handle_match_winner(msg):
    uid = msg.from_user.id
    data = match_registration[uid]
    text = msg.text.strip().upper()
    if text == "CT":
        data["winner"] = "ct"
    elif text == "T":
        data["winner"] = "t"
    else:
        bot.send_message(uid, "❌ Напишите CT или T")
        return
    data["step"] = "stats_ct"
    bot.send_message(uid, "Введите статистику CT (5 игроков, формат: ID K A D):")

@bot.message_handler(func=lambda m: m.from_user.id in match_registration and match_registration[m.from_user.id].get("step") == "stats_ct")
def handle_stats_ct(msg):
    uid = msg.from_user.id
    data = match_registration[uid]
    lines = msg.text.strip().split('\n')
    stats = []
    for line in lines:
        parts = line.strip().split()
        if len(parts) >= 4:
            try:
                stats.append({"user_id": int(parts[0]), "kills": int(parts[1]), "assists": int(parts[2]), "deaths": int(parts[3])})
            except:
                pass
    if len(stats) != 5:
        bot.send_message(uid, f"❌ Получено {len(stats)} игроков, нужно 5. Попробуйте ещё раз:")
        return
    data["stats_ct"] = stats
    data["step"] = "stats_t"
    bot.send_message(uid, "✅ Статистика CT сохранена!\n\nВведите статистику T (5 игроков):")

@bot.message_handler(func=lambda m: m.from_user.id in match_registration and match_registration[m.from_user.id].get("step") == "stats_t")
def handle_stats_t(msg):
    uid = msg.from_user.id
    data = match_registration[uid]
    lobby = active_lobbies.get(data["lobby_id"])
    lines = msg.text.strip().split('\n')
    stats = []
    for line in lines:
        parts = line.strip().split()
        if len(parts) >= 4:
            try:
                stats.append({"user_id": int(parts[0]), "kills": int(parts[1]), "assists": int(parts[2]), "deaths": int(parts[3])})
            except:
                pass
    if len(stats) != 5:
        bot.send_message(uid, f"❌ Получено {len(stats)} игроков, нужно 5")
        return
    data["stats_t"] = stats
    process_match_result(uid, data, lobby)
    del match_registration[uid]

def process_match_result(admin_uid, data, lobby):
    winner = data["winner"]
    score_w = data["score_w"]
    score_l = data["score_l"]
    all_stats = {}
    for s in data["stats_ct"]:
        all_stats[s["user_id"]] = {"kills": s["kills"], "assists": s["assists"], "deaths": s["deaths"], "won": winner == "ct"}
    for s in data["stats_t"]:
        all_stats[s["user_id"]] = {"kills": s["kills"], "assists": s["assists"], "deaths": s["deaths"], "won": winner == "t"}
    results = f"📊 РЕЗУЛЬТАТЫ МАТЧА\n\nКарта: {lobby['map_name']}\nПобедитель: {'CT' if winner=='ct' else 'T'}\nСчёт: {score_w}:{score_l}\n\n"
    for uid, s in all_stats.items():
        p = get_player(uid)
        name = p[1] if p else str(uid)
        kills = s["kills"]
        if s["won"]:
            elo_change = 17
            coins = random.randint(10, 20)
            result = "ПОБЕДА"
        else:
            elo_change = -15 if kills >= 11 else -25
            coins = random.randint(5, 6)
            result = "ПОРАЖЕНИЕ"
        update_player_stats(uid, kills, s["deaths"], s["assists"], s["won"], coins)
        results += f"\n{name}: {result} | {elo_change:+d} ELO | {kills}/{s['deaths']}/{s['assists']} | +{coins} монет\n"
    for uid in lobby["players"]:
        try:
            bot.send_message(uid, results, parse_mode="HTML")
        except:
            pass
    lobby["status"] = "finished"
    del active_lobbies[lobby["id"]]
    bot.send_message(admin_uid, "✅ Матч зарегистрирован!")

# ==================== ДОБАВЛЕНИЕ БОТОВ ====================
@bot.callback_query_handler(func=lambda c: c.data == "add_bots_admin")
def cb_add_bots_admin(c):
    uid = c.from_user.id
    if not is_admin(uid):
        bot.answer_callback_query(c.id, "❌ Нет доступа")
        return
    if not active_lobbies:
        bot.edit_message_text("❌ Нет активных лобби", c.message.chat.id, c.message.message_id)
        bot.answer_callback_query(c.id)
        return
    text = "🤖 Выбери лобби:\n"
    kb = types.InlineKeyboardMarkup(row_width=1)
    for lobby_id, lobby in active_lobbies.items():
        if lobby["status"] == "waiting":
            text += f"• {lobby_id} — {len(lobby['players'])}/10\n"
            kb.add(types.InlineKeyboardButton(f"➕ {lobby_id}", callback_data=f"fill_bots_{lobby_id}"))
    bot.edit_message_text(text, c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("fill_bots_"))
def cb_fill_bots(c):
    lobby_id = c.data.split("_", 2)[2]
    uid = c.from_user.id
    if not is_admin(uid):
        bot.answer_callback_query(c.id, "❌ Нет доступа")
        return
    lobby = active_lobbies.get(lobby_id)
    if not lobby:
        bot.answer_callback_query(c.id, "❌ Лобби не найдено")
        return
    bots = get_bots()
    added = 0
    for bot_id, bot_name in bots:
        if len(lobby["players"]) >= 10:
            break
        if bot_id not in lobby["players"]:
            lobby["players"].append(bot_id)
            user_lobby[bot_id] = lobby_id
            added += 1
    bot.answer_callback_query(c.id, f"✅ Добавлено {added} ботов в лобби {lobby_id}!")

# ==================== ОСТАЛЬНЫЕ КНОПКИ ====================
@bot.callback_query_handler(func=lambda c: c.data in ["top", "shop", "inv"])
def cb_other(c):
    bot.edit_message_text(f"🚧 {c.data} в разработке", c.message.chat.id, c.message.message_id)
    bot.answer_callback_query(c.id)

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    init_db()
    print("✅ ACTUAL FACEIT Bot запущен!")
    bot.infinity_polling(skip_pending=True)