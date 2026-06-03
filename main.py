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
    # Добавляем админа
    cur.execute("INSERT OR IGNORE INTO players (user_id, username, registered, is_admin) VALUES (?, 'Admin', 1, 1)", (ADMIN_ID,))
    # Добавляем тестовых ботов (если нет)
    for i in range(1, 21):
        bot_id = 100000000 + i
        cur.execute("INSERT OR IGNORE INTO players (user_id, username, game_id, device, registered, is_bot, elo) VALUES (?, ?, ?, ?, 1, 1, 1000)", 
                   (bot_id, f"Bot_{i}", str(500000 + i), "PC" if i % 2 == 0 else "MOBILE"))
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

def get_bots():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT user_id, username FROM players WHERE is_bot=1")
    bots = cur.fetchall()
    conn.close()
    return bots

# ==================== ГЛАВНОЕ МЕНЮ ====================
def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        types.InlineKeyboardButton("🎮 Найти матч", callback_data="find"),
        types.InlineKeyboardButton("🏆 Топ", callback_data="top"),
        types.InlineKeyboardButton("🛒 Магазин", callback_data="shop"),
        types.InlineKeyboardButton("🎒 Инвентарь", callback_data="inv")
    )
    return kb

# ==================== РЕГИСТРАЦИЯ ====================
user_flow = {}

@bot.message_handler(commands=['start'])
def cmd_start(msg):
    uid = msg.from_user.id
    
    if is_registered(uid):
        bot.send_message(uid, "⚡ ACTUAL FACEIT", reply_markup=main_menu())
        return
    
    user_flow[uid] = {"state": "nick"}
    bot.send_message(uid, "👋 Добро пожаловать!\n\n<b>Шаг 1:</b> Введи свой никнейм (2-20 символов):", parse_mode="HTML")

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
    bot.send_message(uid, f"✅ <b>Регистрация завершена!</b>\n\nНик: {data['nick']}\nGame ID: {data['game_id']}\nDevice: {device}", reply_markup=kb_remove, parse_mode="HTML")
    bot.send_message(uid, "⚡ ACTUAL FACEIT", reply_markup=main_menu())

# ==================== ПРОФИЛЬ ====================
def get_profile_text(uid):
    p = get_player(uid)
    if not p:
        return "❌ Ошибка"
    
    games = p[6] + p[7]
    winrate = round(p[6] / games * 100, 1) if games > 0 else 0
    kd = round(p[8] / p[9], 2) if p[9] > 0 else p[8]
    
    return (f"👤 <b>{p[1]}</b>\n"
            f"🆔 ID: {p[0]}\n"
            f"🎮 Game ID: {p[2]}\n"
            f"📱 Device: {p[3]}\n"
            f"📊 ELO: {p[4]}\n"
            f"💰 Монет: {p[5]}\n\n"
            f"🏆 Побед: {p[6]}\n"
            f"❌ Поражений: {p[7]}\n"
            f"🔫 Убийств: {p[8]}\n"
            f"💀 Смертей: {p[9]}\n"
            f"🤝 Ассистов: {p[10]}\n"
            f"📊 K/D: {kd}\n"
            f"📈 Винрейт: {winrate}%")

@bot.callback_query_handler(func=lambda c: c.data == "profile")
def cb_profile(c):
    text = get_profile_text(c.from_user.id)
    bot.edit_message_text(text, c.message.chat.id, c.message.message_id, parse_mode="HTML")
    bot.answer_callback_query(c.id)

# ==================== ЛОББИ (4 РЯДА) ====================
active_lobbies = {}
user_lobby = {}

@bot.callback_query_handler(func=lambda c: c.data == "find")
def cb_find(c):
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
    bot.edit_message_text("⚡ ACTUAL FACEIT", c.message.chat.id, c.message.message_id, reply_markup=main_menu())
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("lobby_") and not c.data.startswith("lobby_page2_"))
def cb_lobby(c):
    league = c.data.split("_")[1]
    
    # Собираем данные по всем лобби
    lobbies_text = ""
    for slot in range(1, 11):
        mobile_id = f"{league}_mobile_{slot}"
        pc_id = f"{league}_pc_{slot}"
        mobile_count = len(active_lobbies.get(mobile_id, {}).get("players", []))
        pc_count = len(active_lobbies.get(pc_id, {}).get("players", []))
        mobile_emoji = "🟢" if mobile_count > 0 else "⚪"
        pc_emoji = "🟢" if pc_count > 0 else "⚪"
        lobbies_text += f"Лобби #{slot}:  {mobile_emoji} Mobile ({mobile_count}/10)  |  {pc_emoji} PC ({pc_count}/10)\n"
    
    text = f"🎮 <b>ЛОББИ {league.upper()}</b>\n\n{lobbies_text}\n\nВыбери слот:"
    
    kb = types.InlineKeyboardMarkup(row_width=5)
    
    # Ряд Mobile (1-5)
    mobile_row1 = []
    for slot in range(1, 6):
        lobby_id = f"{league}_mobile_{slot}"
        lobby = active_lobbies.get(lobby_id)
        count = len(lobby["players"]) if lobby else 0
        emoji = "🟢" if count > 0 else "⚪"
        mobile_row1.append(types.InlineKeyboardButton(f"{emoji}M{slot}({count})", callback_data=f"join_{league}_mobile_{slot}"))
    kb.row(*mobile_row1)
    
    # Ряд Mobile (6-10)
    mobile_row2 = []
    for slot in range(6, 11):
        lobby_id = f"{league}_mobile_{slot}"
        lobby = active_lobbies.get(lobby_id)
        count = len(lobby["players"]) if lobby else 0
        emoji = "🟢" if count > 0 else "⚪"
        mobile_row2.append(types.InlineKeyboardButton(f"{emoji}M{slot}({count})", callback_data=f"join_{league}_mobile_{slot}"))
    kb.row(*mobile_row2)
    
    # Ряд PC (1-5)
    pc_row1 = []
    for slot in range(1, 6):
        lobby_id = f"{league}_pc_{slot}"
        lobby = active_lobbies.get(lobby_id)
        count = len(lobby["players"]) if lobby else 0
        emoji = "🟢" if count > 0 else "⚪"
        pc_row1.append(types.InlineKeyboardButton(f"{emoji}P{slot}({count})", callback_data=f"join_{league}_pc_{slot}"))
    kb.row(*pc_row1)
    
    # Ряд PC (6-10)
    pc_row2 = []
    for slot in range(6, 11):
        lobby_id = f"{league}_pc_{slot}"
        lobby = active_lobbies.get(lobby_id)
        count = len(lobby["players"]) if lobby else 0
        emoji = "🟢" if count > 0 else "⚪"
        pc_row2.append(types.InlineKeyboardButton(f"{emoji}P{slot}({count})", callback_data=f"join_{league}_pc_{slot}"))
    kb.row(*pc_row2)
    
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="find"))
    
    bot.edit_message_text(text, c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("join_"))
def cb_join(c):
    _, league, device, slot = c.data.split("_")
    slot = int(slot)
    uid = c.from_user.id
    lobby_id = f"{league}_{device}_{slot}"
    
    # Выход из старого лобби
    old = user_lobby.get(uid)
    if old and old in active_lobbies:
        if uid in active_lobbies[old]["players"]:
            active_lobbies[old]["players"].remove(uid)
            if len(active_lobbies[old]["players"]) == 0:
                del active_lobbies[old]
    
    # Создание лобби
    if lobby_id not in active_lobbies:
        active_lobbies[lobby_id] = {
            "players": [],
            "league": league,
            "device": device,
            "slot": slot,
            "status": "waiting"
        }
    
    lobby = active_lobbies[lobby_id]
    
    if lobby["status"] != "waiting":
        bot.answer_callback_query(c.id, "❌ Лобби уже в игре!", show_alert=True)
        return
    
    if len(lobby["players"]) >= 10:
        bot.answer_callback_query(c.id, "❌ Лобби полное!", show_alert=True)
        return
    
    lobby["players"].append(uid)
    user_lobby[uid] = lobby_id
    
    # Показываем состав лобби
    text = f"🎮 <b>Лобби #{slot} ({league.upper()}/{device.upper()})</b>\n👥 Игроков: {len(lobby['players'])}/10\n\n"
    for i, pid in enumerate(lobby["players"], 1):
        p = get_player(pid)
        name = p[1] if p else str(pid)
        text += f"{i}. {name}\n"
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🚪 Выйти из лобби", callback_data=f"leave_{lobby_id}"))
    kb.add(types.InlineKeyboardButton("🔙 К списку", callback_data=f"lobby_{league}"))
    
    bot.edit_message_text(text, c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")
    bot.answer_callback_query(c.id, f"✅ Вы вошли в лобби {slot}!")
    
    # Проверяем, набралось ли 10 человек
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

# ==================== ДОБАВЛЕНИЕ БОТОВ В ЛОББИ ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("add_bots_"))
def cb_add_bots(c):
    uid = c.from_user.id
    if not is_admin(uid):
        bot.answer_callback_query(c.id, "❌ Только администратор может добавлять ботов!")
        return
    
    league = c.data.split("_")[2]
    lobby_id = f"{league}_pc_1"  # Временное лобби
    
    bots = get_bots()
    lobby = active_lobbies.get(lobby_id)
    
    if not lobby:
        bot.answer_callback_query(c.id, "❌ Лобби не найдено")
        return
    
    added = 0
    for bot_id, bot_name in bots:
        if len(lobby["players"]) >= 10:
            break
        if bot_id not in lobby["players"]:
            lobby["players"].append(bot_id)
            user_lobby[bot_id] = lobby_id
            added += 1
    
    bot.answer_callback_query(c.id, f"✅ Добавлено {added} ботов в лобби!")

# ==================== ПРИНЯТИЕ МАТЧА ====================
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
        try:
            bot.send_message(uid, f"⚔️ <b>МАТЧ НАЙДЕН!</b>\n\n⏳ У вас есть {ACCEPT_TIMEOUT} секунд, чтобы принять!\n\nНажмите кнопку ниже:", reply_markup=kb, parse_mode="HTML")
        except:
            pass
        start_accept_timer(lobby_id, uid)

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
        bot.send_message(uid, "⚠️ <b>Вы не приняли матч!</b>\nВы вышли из лобби.", parse_mode="HTML")
    except:
        pass
    
    if len(lobby["players"]) < 10:
        lobby["status"] = "waiting"
        for member_uid in lobby["players"]:
            try:
                bot.send_message(member_uid, "❌ Один из игроков не принял матч. Поиск возобновлён...", parse_mode="HTML")
            except:
                pass
        update_lobby_display(lobby_id)

def update_lobby_display(lobby_id):
    lobby = active_lobbies.get(lobby_id)
    if not lobby:
        return
    
    text = f"🎮 <b>Лобби #{lobby['slot']} ({lobby['league'].upper()}/{lobby['device'].upper()})</b>\n👥 Игроков: {len(lobby['players'])}/10\n\n"
    for i, pid in enumerate(lobby["players"], 1):
        p = get_player(pid)
        name = p[1] if p else str(pid)
        text += f"{i}. {name}\n"
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🚪 Выйти из лобби", callback_data=f"leave_{lobby_id}"))
    kb.add(types.InlineKeyboardButton("🔙 К списку", callback_data=f"lobby_{lobby['league']}"))
    
    for uid in lobby["players"]:
        try:
            bot.send_message(uid, text, reply_markup=kb, parse_mode="HTML")
        except:
            pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("accept_"))
def cb_accept_match(c):
    lobby_id = c.data.split("_", 1)[1]
    uid = c.from_user.id
    lobby = active_lobbies.get(lobby_id)
    
    if not lobby or lobby["status"] != "accept":
        bot.answer_callback_query(c.id, "❌ Матч не найден или уже принят")
        return
    
    if uid not in lobby["players"]:
        bot.answer_callback_query(c.id, "❌ Вы не в этом лобби")
        return
    
    lobby["ready"].add(uid)
    if uid in lobby["accept_timers"]:
        lobby["accept_timers"][uid].cancel()
        del lobby["accept_timers"][uid]
    
    bot.answer_callback_query(c.id, "✅ Вы приняли матч! Ожидаем остальных...")
    
    if len(lobby["ready"]) == len(lobby["players"]):
        for member_uid in lobby["players"]:
            try:
                bot.send_message(member_uid, "✅ Все приняли матч! Начинаем выбор карты...", parse_mode="HTML")
            except:
                pass
        start_veto(lobby_id)

# ==================== ВЕТО КАРТ ====================
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
            bot.send_message(uid, f"🟦 <b>Вы в команде CT!</b>\nКапитан: {get_player(lobby['captain_ct'])[1]}", parse_mode="HTML")
        except:
            pass
    for uid in lobby["team_t"]:
        try:
            bot.send_message(uid, f"🟧 <b>Вы в команде T!</b>\nКапитан: {get_player(lobby['captain_t'])[1]}", parse_mode="HTML")
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
    
    text = f"🗺 <b>ВЫБОР КАРТЫ</b>\n\n"
    text += f"📊 Бан {lobby['ban_count'] + 1}/4\n"
    text += f"🎮 Ход: <b>{'🟦 CT' if turn == 'ct' else '🟧 T'}</b>\n"
    text += f"👑 Капитан: {captain_name}\n\n"
    text += "📋 Доступные карты:\n"
    
    for i, map_name in enumerate(lobby["map_pool"], 1):
        text += f"{i}. {map_name}\n"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    for map_name in lobby["map_pool"]:
        kb.add(types.InlineKeyboardButton(f"❌ Забанить {map_name}", callback_data=f"ban_{lobby_id}_{map_name}"))
    
    for uid in lobby["players"]:
        try:
            if uid == captain:
                bot.send_message(uid, text, reply_markup=kb, parse_mode="HTML")
            else:
                bot.send_message(uid, text, parse_mode="HTML")
        except:
            pass

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
    
    lobby["map_pool"].remove(map_name)
    lobby["bans"].append({"map": map_name, "by": turn})
    lobby["ban_count"] += 1
    
    ban_text = f"🚫 <b>{'CT' if turn == 'ct' else 'T'}</b> забанил <b>{map_name}</b>"
    for member_uid in lobby["players"]:
        try:
            bot.send_message(member_uid, ban_text, parse_mode="HTML")
        except:
            pass
    
    lobby["veto_turn"] = "t" if turn == "ct" else "ct"
    
    if lobby["ban_count"] >= 4 and len(lobby["map_pool"]) == 1:
        final_map = lobby["map_pool"][0]
        final_text = f"✅ <b>Финальная карта: {final_map}</b>"
        for member_uid in lobby["players"]:
            try:
                bot.send_message(member_uid, final_text, parse_mode="HTML")
            except:
                pass
        start_match(lobby_id, final_map)
    else:
        send_veto_message(lobby_id)
    
    bot.answer_callback_query(c.id, f"✅ Карта {map_name} забанена!")

# ==================== НАЧАЛО МАТЧА И РЕГИСТРАЦИЯ РЕЗУЛЬТАТОВ ====================
match_results = {}  # lobby_id -> {"winner": str, "score_ct": int, "score_t": int, "stats": dict}

def start_match(lobby_id, map_name):
    lobby = active_lobbies.get(lobby_id)
    if not lobby:
        return
    
    lobby["status"] = "active"
    lobby["map_name"] = map_name
    lobby["match_start_time"] = time.time()
    
    text = f"⚔️ <b>МАТЧ НАЧАЛСЯ!</b>\n\n"
    text += f"🗺 Карта: {map_name}\n"
    text += f"🏆 Лига: {lobby['league'].upper()}\n\n"
    text += f"🟦 <b>КОМАНДА CT</b>\n"
    for i, uid in enumerate(lobby["team_ct"], 1):
        p = get_player(uid)
        name = p[1] if p else str(uid)
        text += f"{i}. {name}\n"
    text += f"\n🟧 <b>КОМАНДА T</b>\n"
    for i, uid in enumerate(lobby["team_t"], 1):
        p = get_player(uid)
        name = p[1] if p else str(uid)
        text += f"{i}. {name}\n"
    text += f"\n📸 После матча нажмите кнопку для отправки результатов!"
    
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
        bot.answer_callback_query(c.id, "❌ Матч не найден или уже завершён")
        return
    
    if not is_admin(uid):
        bot.answer_callback_query(c.id, "❌ Только администратор может регистрировать результат!")
        return
    
    bot.answer_callback_query(c.id)
    match_results[uid] = {"lobby_id": lobby_id, "step": "score"}
    bot.send_message(uid, "📝 <b>Регистрация результата матча</b>\n\nВведите счёт матча.\nФормат: <code>13:11</code>\n\n(где первое число — победитель)", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.from_user.id in match_results and match_results[m.from_user.id].get("step") == "score")
def handle_match_score(msg):
    uid = msg.from_user.id
    data = match_results[uid]
    lobby_id = data["lobby_id"]
    lobby = active_lobbies.get(lobby_id)
    
    if not lobby:
        bot.send_message(uid, "❌ Матч не найден")
        del match_results[uid]
        return
    
    try:
        score_parts = msg.text.strip().split(":")
        score_w = int(score_parts[0])
        score_l = int(score_parts[1])
        
        if score_w > score_l:
            winner = "ct" if score_w > score_l else "t"
        else:
            # Если счёт равный, спрашиваем победителя
            match_results[uid]["score_w"] = score_w
            match_results[uid]["score_l"] = score_l
            match_results[uid]["step"] = "winner"
            bot.send_message(uid, "Счёт равный! Кто победил?\n\nНапишите <b>CT</b> или <b>T</b>", parse_mode="HTML")
            return
        
        match_results[uid]["score_w"] = score_w
        match_results[uid]["score_l"] = score_l
        match_results[uid]["winner"] = winner
        match_results[uid]["step"] = "stats_ct"
        bot.send_message(uid, f"✅ Счёт {score_w}:{score_l}\n\nТеперь введите статистику команды <b>CT</b>\n\nФормат для каждого игрока:\n<code>ID игрока Убийства Ассисты Смерти</code>\n\nПример:\n<code>8521250777 18 5 2</code>\n\nВведите статистику для ВСЕХ 5 игроков CT по одному на строку:", parse_mode="HTML")
    except:
        bot.send_message(uid, "❌ Неверный формат! Используйте: 13:11")

@bot.message_handler(func=lambda m: m.from_user.id in match_results and match_results[m.from_user.id].get("step") == "winner")
def handle_match_winner(msg):
    uid = msg.from_user.id
    data = match_results[uid]
    text = msg.text.strip().upper()
    
    if text == "CT":
        data["winner"] = "ct"
    elif text == "T":
        data["winner"] = "t"
    else:
        bot.send_message(uid, "❌ Напишите CT или T")
        return
    
    data["step"] = "stats_ct"
    bot.send_message(uid, f"✅ Победитель: {text}\n\nТеперь введите статистику команды <b>CT</b>\n\nФормат для каждого игрока:\n<code>ID игрока Убийства Ассисты Смерти</code>\n\nВведите статистику для ВСЕХ 5 игроков CT по одному на строку:", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.from_user.id in match_results and match_results[m.from_user.id].get("step") == "stats_ct")
def handle_stats_ct(msg):
    uid = msg.from_user.id
    data = match_results[uid]
    
    lines = msg.text.strip().split('\n')
    stats = []
    for line in lines:
        parts = line.strip().split()
        if len(parts) >= 4:
            try:
                stats.append({
                    "user_id": int(parts[0]),
                    "kills": int(parts[1]),
                    "assists": int(parts[2]),
                    "deaths": int(parts[3])
                })
            except:
                pass
    
    if len(stats) != 5:
        bot.send_message(uid, f"❌ Получено {len(stats)} игроков, нужно 5. Попробуйте ещё раз:")
        return
    
    data["stats_ct"] = stats
    data["step"] = "stats_t"
    bot.send_message(uid, "✅ Статистика CT сохранена!\n\nТеперь введите статистику команды <b>T</b> (5 игроков):", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.from_user.id in match_results and match_results[m.from_user.id].get("step") == "stats_t")
def handle_stats_t(msg):
    uid = msg.from_user.id
    data = match_results[uid]
    lobby_id = data["lobby_id"]
    lobby = active_lobbies.get(lobby_id)
    
    lines = msg.text.strip().split('\n')
    stats = []
    for line in lines:
        parts = line.strip().split()
        if len(parts) >= 4:
            try:
                stats.append({
                    "user_id": int(parts[0]),
                    "kills": int(parts[1]),
                    "assists": int(parts[2]),
                    "deaths": int(parts[3])
                })
            except:
                pass
    
    if len(stats) != 5:
        bot.send_message(uid, f"❌ Получено {len(stats)} игроков, нужно 5. Попробуйте ещё раз:")
        return
    
    data["stats_t"] = stats
    
    # Начисляем ELO и монеты
    process_match_result(uid, data, lobby)
    del match_results[uid]

def process_match_result(admin_uid, data, lobby):
    score_w = data["score_w"]
    score_l = data["score_l"]
    winner = data["winner"]
    stats_ct = data["stats_ct"]
    stats_t = data["stats_t"]
    
    all_stats = {}
    for s in stats_ct:
        all_stats[s["user_id"]] = {"kills": s["kills"], "assists": s["assists"], "deaths": s["deaths"], "side": "ct", "won": winner == "ct"}
    for s in stats_t:
        all_stats[s["user_id"]] = {"kills": s["kills"], "assists": s["assists"], "deaths": s["deaths"], "side": "t", "won": winner == "t"}
    
    results_text = f"📊 <b>РЕЗУЛЬТАТЫ МАТЧА</b>\n\n"
    results_text += f"🗺 Карта: {lobby['map_name']}\n"
    results_text += f"🏆 Победитель: {'CT' if winner == 'ct' else 'T'}\n"
    results_text += f"📋 Счёт: {score_w}:{score_l}\n\n"
    
    for uid, stats in all_stats.items():
        p = get_player(uid)
        name = p[1] if p else str(uid)
        
        # Начисление ELO
        current_elo = p[4] if p else 1000
        kills = stats["kills"]
        
        if stats["won"]:
            elo_change = 17
            result_text = "🏆 ПОБЕДА"
            coins = random.randint(10, 20)
        else:
            if kills >= 11:
                elo_change = -15
            else:
                elo_change = -25
            result_text = "💀 ПОРАЖЕНИЕ"
            coins = random.randint(5, 6)
        
        new_elo = current_elo + elo_change
        
        # Обновляем БД
        conn = sqlite3.connect(DB)
        conn.execute("UPDATE players SET elo=?, wins=wins+?, losses=losses+?, kills=kills+?, deaths=deaths+?, assists=assists+?, coins=coins+? WHERE user_id=?", 
                    (new_elo, 1 if stats["won"] else 0, 0 if stats["won"] else 1, 
                     stats["kills"], stats["deaths"], stats["assists"], coins, uid))
        conn.commit()
        conn.close()
        
        results_text += f"\n👤 {name}\n"
        results_text += f"📊 {result_text} | {elo_change:+d} ELO\n"
        results_text += f"🔫 {stats['kills']}/{stats['deaths']}/{stats['assists']} | 💰 +{coins} монет\n"
    
    # Отправляем результаты всем игрокам
    for uid in lobby["players"]:
        try:
            bot.send_message(uid, results_text, parse_mode="HTML")
        except:
            pass
    
    # Завершаем матч
    lobby["status"] = "finished"
    del active_lobbies[lobby_id]
    
    bot.send_message(admin_uid, "✅ Матч успешно зарегистрирован! Статистика сохранена.")

# ==================== ДОБАВЛЕНИЕ БОТОВ В ЛОББИ (АДМИН) ====================
@bot.callback_query_handler(func=lambda c: c.data == "add_bots_admin")
def cb_add_bots_admin(c):
    uid = c.from_user.id
    if not is_admin(uid):
        bot.answer_callback_query(c.id, "❌ Нет доступа")
        return
    
    # Показываем список лобби для добавления ботов
    text = "🤖 <b>Добавление ботов в лобби</b>\n\nВыбери лобби:"
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    for league in ["default", "quals"]:
        for device in ["mobile", "pc"]:
            for slot in range(1, 6):
                lobby_id = f"{league}_{device}_{slot}"
                count = len(active_lobbies.get(lobby_id, {}).get("players", []))
                kb.add(types.InlineKeyboardButton(f"{league.upper()} {device} {slot} ({count}/10)", callback_data=f"add_bots_to_{lobby_id}"))
    
    bot.edit_message_text(text, c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("add_bots_to_"))
def cb_add_bots_to(c):
    lobby_id = c.data.split("_", 4)[4]
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
    
    bot.answer_callback_query(c.id, f"✅ Добавлено {added} ботов в лобби!")

# ==================== ОСТАЛЬНЫЕ КНОПКИ ====================
@bot.callback_query_handler(func=lambda c: c.data in ["top", "shop", "inv"])
def cb_other(c):
    bot.edit_message_text(f"🚧 {c.data} в разработке", c.message.chat.id, c.message.message_id)
    bot.answer_callback_query(c.id)

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    init_db()
    print("✅ ACTUAL FACEIT Bot запущен!")
    print(f"Админ: {ADMIN_ID}")
    print(f"Ботов в базе: {len(get_bots())}")
    bot.infinity_polling(skip_pending=True)