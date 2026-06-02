import telebot
from telebot import types
import sqlite3
import random
from datetime import datetime

# ==================== КОНФИГ ====================
TOKEN = "8992378453:AAE5chyJsnbcPHS1YMZ03BWoCR8XKllcSfA"  # Вставь сюда новый токен от @BotFather
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
    return p is not None and p[14] == 1

# ==================== ПРОВЕРКИ ====================
def check_reg(uid, chat_id):
    if is_registered(uid):
        return True
    bot.send_message(chat_id, "❌ Вы не зарегистрированы! Напишите /start")
    return False

# ==================== ГЛАВНОЕ МЕНЮ ====================
def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"),
        types.InlineKeyboardButton("🎮 Найти матч", callback_data="menu_find"),
        types.InlineKeyboardButton("🏆 Топ", callback_data="menu_top"),
        types.InlineKeyboardButton("🛒 Магазин", callback_data="menu_shop"),
        types.InlineKeyboardButton("🎒 Инвентарь", callback_data="menu_inv"),
        types.InlineKeyboardButton("⚙️ Админ панель", callback_data="menu_admin")
    )
    return kb

# ==================== РЕГИСТРАЦИЯ ====================
user_flow = {}

@bot.message_handler(commands=['start'])
def cmd_start(msg):
    uid = msg.from_user.id
    if is_registered(uid):
        bot.send_message(uid, "⚡ Добро пожаловать!", reply_markup=main_menu())
        return
    
    user_flow[uid] = {"state": "reg_nick"}
    bot.send_message(uid, "👋 Добро пожаловать!\n\nШаг 1: Введи свой никнейм:")

@bot.message_handler(func=lambda m: user_flow.get(m.from_user.id, {}).get("state") == "reg_nick")
def reg_nick(msg):
    uid = msg.from_user.id
    nick = msg.text.strip()
    if not (2 <= len(nick) <= 20):
        bot.send_message(uid, "❌ Никнейм 2-20 символов")
        return
    user_flow[uid] = {"state": "reg_id", "nick": nick}
    bot.send_message(uid, "📋 Шаг 2: Введи свой игровой ID (только цифры):")

@bot.message_handler(func=lambda m: user_flow.get(m.from_user.id, {}).get("state") == "reg_id")
def reg_id(msg):
    uid = msg.from_user.id
    game_id = msg.text.strip()
    if not game_id.isdigit():
        bot.send_message(uid, "❌ ID только цифры")
        return
    user_flow[uid]["game_id"] = game_id
    user_flow[uid]["state"] = "reg_device"
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.row("MOBILE", "PC")
    bot.send_message(uid, "📱 Шаг 3: Выбери устройство:", reply_markup=kb)

@bot.message_handler(func=lambda m: user_flow.get(m.from_user.id, {}).get("state") == "reg_device")
def reg_device(msg):
    uid = msg.from_user.id
    device = msg.text.strip()
    if device not in ("MOBILE", "PC"):
        bot.send_message(uid, "❌ Выбери MOBILE или PC")
        return
    
    data = user_flow.pop(uid)
    register_user(uid, data["nick"], data["game_id"], device)
    
    kb_remove = types.ReplyKeyboardRemove()
    bot.send_message(uid, f"✅ Регистрация завершена!\n\nНик: {data['nick']}\nID: {data['game_id']}\nDevice: {device}", reply_markup=kb_remove)
    bot.send_message(uid, "⚡ Добро пожаловать!", reply_markup=main_menu())

# ==================== ОБРАБОТЧИК МЕНЮ ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("menu_"))
def cb_menu(c):
    uid = c.from_user.id
    action = c.data.split("_")[1]
    
    if not check_reg(uid, c.message.chat.id):
        bot.answer_callback_query(c.id)
        return
    
    if action == "profile":
        p = get_player(uid)
        if p:
            text = (f"👤 <b>{p[1]}</b>\n"
                   f"🆔 ID: {p[0]}\n"
                   f"🎮 Game ID: {p[2]}\n"
                   f"📱 Device: {p[3]}\n"
                   f"⭐ LVL: {p[4]}\n"
                   f"📊 ELO: {p[5]}\n"
                   f"💰 Монет: {p[6]}\n"
                   f"🏆 Побед: {p[7]} | ❌ Поражений: {p[8]}")
            bot.edit_message_text(text, c.message.chat.id, c.message.message_id, parse_mode="HTML")
        else:
            bot.edit_message_text("❌ Ошибка", c.message.chat.id, c.message.message_id)
    else:
        bot.edit_message_text(f"📌 {action} — в разработке", c.message.chat.id, c.message.message_id)
    
    bot.answer_callback_query(c.id)

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    init_db()
    print("✅ Бот запущен!")
    bot.infinity_polling(skip_pending=True)