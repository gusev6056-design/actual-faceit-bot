import os
import telebot
from telebot import types
import sqlite3
from flask import Flask
import threading

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
            is_admin INTEGER DEFAULT 0,
            registered INTEGER DEFAULT 0
        )
    ''')
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
    return p is not None and p[9] == 1

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
@bot.callback_query_handler(func=lambda c: c.data == "profile")
def cb_profile(c):
    uid = c.from_user.id
    p = get_player(uid)
    if not p:
        bot.edit_message_text("❌ Ошибка", c.message.chat.id, c.message.message_id)
        bot.answer_callback_query(c.id)
        return
    
    games = p[6] + p[7]
    winrate = round(p[6] / games * 100, 1) if games > 0 else 0
    
    text = (f"👤 <b>{p[1]}</b>\n"
            f"🆔 ID: {p[0]}\n"
            f"🎮 Game ID: {p[2]}\n"
            f"📱 Device: {p[3]}\n"
            f"📊 ELO: {p[4]}\n"
            f"💰 Монет: {p[5]}\n\n"
            f"🏆 Побед: {p[6]}\n"
            f"❌ Поражений: {p[7]}\n"
            f"📈 Винрейт: {winrate}%")
    
    bot.edit_message_text(text, c.message.chat.id, c.message.message_id, parse_mode="HTML")
    bot.answer_callback_query(c.id)

# ==================== ЛОББИ (2 РЯДА) ====================
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

@bot.callback_query_handler(func=lambda c: c.data.startswith("lobby_"))
def cb_lobby(c):
    league = c.data.split("_")[1]
    
    # Кнопки 1-5
    kb = types.InlineKeyboardMarkup(row_width=5)
    
    # Ряд MOBILE (1-5)
    mobile_btns = []
    for slot in range(1, 6):
        lobby_id = f"{league}_mobile_{slot}"
        lobby = active_lobbies.get(lobby_id)
        count = len(lobby["players"]) if lobby else 0
        emoji = "🟢" if count > 0 else "⚪"
        mobile_btns.append(types.InlineKeyboardButton(f"{emoji}M{slot}({count})", callback_data=f"join_{league}_mobile_{slot}"))
    kb.row(*mobile_btns)
    
    # Ряд PC (1-5)
    pc_btns = []
    for slot in range(1, 6):
        lobby_id = f"{league}_pc_{slot}"
        lobby = active_lobbies.get(lobby_id)
        count = len(lobby["players"]) if lobby else 0
        emoji = "🟢" if count > 0 else "⚪"
        pc_btns.append(types.InlineKeyboardButton(f"{emoji}P{slot}({count})", callback_data=f"join_{league}_pc_{slot}"))
    kb.row(*pc_btns)
    
    # Кнопки 6-10 и назад
    kb.add(types.InlineKeyboardButton("➡️ Лобби 6-10", callback_data=f"lobby_page2_{league}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="find"))
    
    bot.edit_message_text(f"🎮 <b>ЛОББИ {league.upper()}</b>\n\nВыбери слот:", c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith("lobby_page2_"))
def cb_lobby_page2(c):
    league = c.data.split("_")[2]
    
    kb = types.InlineKeyboardMarkup(row_width=5)
    
    # Ряд MOBILE (6-10)
    mobile_btns = []
    for slot in range(6, 11):
        lobby_id = f"{league}_mobile_{slot}"
        lobby = active_lobbies.get(lobby_id)
        count = len(lobby["players"]) if lobby else 0
        emoji = "🟢" if count > 0 else "⚪"
        mobile_btns.append(types.InlineKeyboardButton(f"{emoji}M{slot}({count})", callback_data=f"join_{league}_mobile_{slot}"))
    kb.row(*mobile_btns)
    
    # Ряд PC (6-10)
    pc_btns = []
    for slot in range(6, 11):
        lobby_id = f"{league}_pc_{slot}"
        lobby = active_lobbies.get(lobby_id)
        count = len(lobby["players"]) if lobby else 0
        emoji = "🟢" if count > 0 else "⚪"
        pc_btns.append(types.InlineKeyboardButton(f"{emoji}P{slot}({count})", callback_data=f"join_{league}_pc_{slot}"))
    kb.row(*pc_btns)
    
    kb.add(types.InlineKeyboardButton("⬅️ Лобби 1-5", callback_data=f"lobby_{league}"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="find"))
    
    bot.edit_message_text(f"🎮 <b>ЛОББИ {league.upper()}</b>\n\nВыбери слот:", c.message.chat.id, c.message.message_id, reply_markup=kb, parse_mode="HTML")
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
            "slot": slot
        }
    
    lobby = active_lobbies[lobby_id]
    
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