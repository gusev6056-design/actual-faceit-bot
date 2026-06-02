import telebot
from telebot import types
import sqlite3
import random
from datetime import datetime

# ==================== КОНФИГ ====================
TOKEN = "8992378453:AAE5chyJsnbcPHS1YMZ03BWoCR8XKllcSfA"
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
            level INTEGER DEFAULT 1,
            elo INTEGER DEFAULT 1000,
            coins INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            kills INTEGER DEFAULT 0,
            deaths INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            registered INTEGER DEFAULT 0,
            warns INTEGER DEFAULT 0,
            muted_until TEXT DEFAULT NULL,
            banned INTEGER DEFAULT 0,
            calibration_matches INTEGER DEFAULT 0
        )
    ''')
    
    # Добавляем админа если нет
    cur.execute("SELECT * FROM players WHERE user_id=?", (ADMIN_ID,))
    if not cur.fetchone():
        cur.execute("INSERT INTO players (user_id, username, registered, is_admin) VALUES (?, 'Admin', 1, 1)", (ADMIN_ID,))
    
    conn.commit()
    conn.close()

def register_user(user_id, username, game_id, device):
    conn = sqlite3.connect(DB)
    conn.execute('''
        INSERT OR REPLACE INTO players 
        (user_id, username, game_id, device, registered, coins, elo, level)
        VALUES (?, ?, ?, ?, 1, 100, 1000, 1)
    ''', (user_id, username, game_id, device))
    conn.commit()
    conn.close()
    return True

def get_player(user_id):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT * FROM players WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row

def is_registered(user_id):
    p = get_player(user_id)
    if not p:
        return False
    # registered - это 14-й столбец (считаем с 0)
    return p[14] == 1

def update_player_stats(user_id, kills, deaths, assists, win):
    conn = sqlite3.connect(DB)
    if win:
        conn.execute("UPDATE players SET wins=wins+1, kills=kills+?, deaths=deaths+?, assists=assists+? WHERE user_id=?", 
                     (kills, deaths, assists, user_id))
    else:
        conn.execute("UPDATE players SET losses=losses+1, kills=kills+?, deaths=deaths+?, assists=assists+? WHERE user_id=?", 
                     (kills, deaths, assists, user_id))
    conn.commit()
    conn.close()

# ==================== ПРОВЕРКИ ====================
def check_reg(uid, chat_id):
    if is_registered(uid):
        return True
    bot.send_message(chat_id, "❌ Вы не зарегистрированы! Напишите /start")
    return False

def is_admin(uid):
    p = get_player(uid)
    return p is not None and p[12] == 1  # is_admin - 12-й столбец

# ==================== ГЛАВНОЕ МЕНЮ ====================
def main_menu(uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"),
        types.InlineKeyboardButton("🎮 Найти матч", callback_data="menu_find"),
        types.InlineKeyboardButton("🏆 Топ", callback_data="menu_top"),
        types.InlineKeyboardButton("🛒 Магазин", callback_data="menu_shop"),
        types.InlineKeyboardButton("🎒 Инвентарь", callback_data="menu_inv")
    )
    if is_admin(uid):
        kb.add(types.InlineKeyboardButton("⚙️ Админ панель", callback_data="menu_admin"))
    return kb

# ==================== РЕГИСТРАЦИЯ ====================
user_flow = {}

@bot.message_handler(commands=['start'])
def cmd_start(msg):
    uid = msg.from_user.id
    if is_registered(uid):
        bot.send_message(uid, "⚡ Добро пожаловать в ACTUAL FACEIT!", reply_markup=main_menu(uid))
        return
    
    user_flow[uid] = {"state": "reg_nick"}
    bot.send_message(uid, "👋 Добро пожаловать в ACTUAL FACEIT!\n\n<b>Шаг 1:</b> Введи свой никнейм:", parse_mode="HTML")

@bot.message_handler(func=lambda m: user_flow.get(m.from_user.id, {}).get("state") == "reg_nick")
def reg_nick(msg):
    uid = msg.from_user.id
    nick = msg.text.strip()
    if not (2 <= len(nick) <= 20):
        bot.send_message(uid, "❌ Никнейм должен быть 2-20 символов. Попробуй ещё раз:")
        return
    user_flow[uid] = {"state": "reg_id", "nick": nick}
    bot.send_message(uid, "<b>Шаг 2:</b> Введи свой игровой ID (только цифры):", parse_mode="HTML")

@bot.message_handler(func=lambda m: user_flow.get(m.from_user.id, {}).get("state") == "reg_id")
def reg_id(msg):
    uid = msg.from_user.id
    game_id = msg.text.strip()
    if not game_id.isdigit():
        bot.send_message(uid, "❌ ID должен содержать только цифры. Попробуй ещё раз:")
        return
    user_flow[uid]["game_id"] = game_id
    user_flow[uid]["state"] = "reg_device"
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row("MOBILE", "PC")
    bot.send_message(uid, "<b>Шаг 3:</b> Выбери устройство:", reply_markup=kb, parse_mode="HTML")

@bot.message_handler(func=lambda m: user_flow.get(m.from_user.id, {}).get("state") == "reg_device")
def reg_device(msg):
    uid = msg.from_user.id
    device = msg.text.strip()
    if device not in ("MOBILE", "PC"):
        bot.send_message(uid, "❌ Выбери MOBILE или PC")
        return
    
    data = user_flow.pop(uid)
    register_user(uid, data["nick"], data["game_id"], device)
    
    # Убираем клавиатуру
    kb_remove = types.ReplyKeyboardRemove()
    bot.send_message(uid, f"✅ <b>Регистрация завершена!</b>\n\nНик: {data['nick']}\nID: {data['game_id']}\nDevice: {device}", reply_markup=kb_remove, parse_mode="HTML")
    bot.send_message(uid, "⚡ Добро пожаловать в ACTUAL FACEIT!", reply_markup=main_menu(uid))

# ==================== ПРОФИЛЬ ====================
def get_profile_text(uid):
    p = get_player(uid)
    if not p:
        return "❌ Ошибка"
    
    games = p[7] + p[8]  # wins + losses
    kd = round(p[9] / p[10], 2) if p[10] > 0 else p[9]
    winrate = round(p[7] / games * 100, 1) if games > 0 else 0
    
    text = (f"👤 <b>{p[1]}</b>\n"
            f"🆔 ID: {p[0]}\n"
            f"🎮 Game ID: {p[2]}\n"
            f"📱 Device: {p[3]}\n"
            f"⭐ Уровень: {p[4]}\n"
            f"📊 ELO: {p[5]}\n"
            f"💰 Монет: {p[6]}\n\n"
            f"📈 <b>Статистика</b>\n"
            f"🏆 Побед: {p[7]}\n"
            f"❌ Поражений: {p[8]}\n"
            f"📊 K/D: {kd}\n"
            f"📈 Винрейт: {winrate}%\n"
            f"🔫 Убийств: {p[9]}\n"
            f"💀 Смертей: {p[10]}\n"
            f"🤝 Ассистов: {p[11]}")
    return text

# ==================== ОБРАБОТЧИК МЕНЮ ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("menu_"))
def cb_menu(c):
    uid = c.from_user.id
    action = c.data.split("_")[1]
    
    if not check_reg(uid, c.message.chat.id):
        bot.answer_callback_query(c.id)
        return
    
    if action == "profile":
        text = get_profile_text(uid)
        bot.edit_message_text(text, c.message.chat.id, c.message.message_id, parse_mode="HTML")
    
    elif action == "find":
        bot.edit_message_text("🎮 Поиск матча (в разработке)", c.message.chat.id, c.message.message_id)
    
    elif action == "top":
        bot.edit_message_text("🏆 Топ игроков (скоро)", c.message.chat.id, c.message.message_id)
    
    elif action == "shop":
        bot.edit_message_text("🛒 Магазин (скоро)", c.message.chat.id, c.message.message_id)
    
    elif action == "inv":
        bot.edit_message_text("🎒 Инвентарь (скоро)", c.message.chat.id, c.message.message_id)
    
    elif action == "admin" and is_admin(uid):
        bot.edit_message_text("⚙️ Админ панель (скоро)", c.message.chat.id, c.message.message_id)
    
    else:
        bot.edit_message_text("В разработке", c.message.chat.id, c.message.message_id)
    
    bot.answer_callback_query(c.id)

# ==================== КОМАНДА /DEBUG ====================
@bot.message_handler(commands=['debug'])
def cmd_debug(msg):
    uid = msg.from_user.id
    p = get_player(uid)
    if p:
        text = f"Player: {p[1]}\nRegistered: {p[14]}\nIs Admin: {p[12]}"
        bot.send_message(uid, text)
    else:
        bot.send_message(uid, "Not found")

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    init_db()
    print("✅ ACTUAL FACEIT Bot запущен!")
    print(f"Admin ID: {ADMIN_ID}")
    bot.infinity_polling(skip_pending=True)