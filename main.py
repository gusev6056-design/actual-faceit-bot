import telebot
from telebot import types
import sqlite3

TOKEN = "8914521673:AAHaGCPmSq5PF6nu9xlEWm2DQe_-qPXx5QI"
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
            coins INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            registered INTEGER DEFAULT 0
        )
    ''')
    cur.execute("INSERT OR IGNORE INTO players (user_id, username, registered, is_admin) VALUES (?, 'Admin', 1, 1)", (ADMIN_ID,))
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
        types.InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"),
        types.InlineKeyboardButton("🎮 Найти матч", callback_data="menu_find"),
        types.InlineKeyboardButton("🏆 Топ", callback_data="menu_top"),
        types.InlineKeyboardButton("🛒 Магазин", callback_data="menu_shop"),
        types.InlineKeyboardButton("🎒 Инвентарь", callback_data="menu_inv")
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
        bot.send_message(uid, "❌ Никнейм должен быть 2-20 символов. Попробуй ещё раз:")
        return
    user_flow[uid] = {"state": "id", "nick": nick}
    bot.send_message(uid, "<b>Шаг 2:</b> Введи свой игровой ID (только цифры):", parse_mode="HTML")

@bot.message_handler(func=lambda m: user_flow.get(m.from_user.id, {}).get("state") == "id")
def reg_id(msg):
    uid = msg.from_user.id
    game_id = msg.text.strip()
    if not game_id.isdigit():
        bot.send_message(uid, "❌ ID должен содержать только цифры. Попробуй ещё раз:")
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
@bot.callback_query_handler(func=lambda c: c.data == "menu_profile")
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

# ==================== ОСТАЛЬНЫЕ КНОПКИ ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("menu_"))
def cb_other(c):
    action = c.data.split("_")[1]
    if action in ["profile"]:
        return  # уже обработано выше
    bot.edit_message_text(f"🚧 {action} в разработке", c.message.chat.id, c.message.message_id)
    bot.answer_callback_query(c.id)

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    init_db()
    print("✅ ACTUAL FACEIT Bot запущен!")
    bot.infinity_polling(skip_pending=True)