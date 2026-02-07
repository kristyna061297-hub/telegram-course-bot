import telebot
import sqlite3
from datetime import datetime, timedelta
from telebot import types
import threading
import time

# ====== НАСТРОЙКИ ======
TOKEN = "8514433226:AAGpKXr7tTFV2kwQLhZtV8wL6s-rEx1w1Cw"
CHANNEL_ID = -1003503105133  # ID закрытого канала

bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

from yookassa import Configuration, Payment
from flask import Flask, request
import uuid

 SHOP_ID = "1260346"
SECRET_KEY = "live_FHvnOehOIHMc4vKsIhokotxm3FKeRP5yYhI8JQOuV70"

Configuration.account_id = SHOP_ID
Configuration.secret_key = SECRET_KEY

# ====== БАЗА ДАННЫХ ======
def get_db():
    conn = sqlite3.connect("users.db", check_same_thread=False)
    return conn, conn.cursor()

def init_db():
    conn, cursor = get_db()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        start_date TEXT,
        end_date TEXT,
        status TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()

def create_payment(user_id):
    payment = Payment.create({
        "amount": {
            "value": "900.00",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/ТВОЙ_БОТ"
        },
        "capture": True,
        "description": f"Подписка на 25 дней",
        "metadata": {
            "user_id": user_id
        }
    }, uuid.uuid4())

    return payment.confirmation.confirmation_url


# ====== КАНАЛ ======
def create_invite_link():
    try:
        link = bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1
        )
        return link.invite_link
    except Exception as e:
        print("Ошибка создания ссылки:", e)
        return None

def remove_from_channel(user_id):
    try:
        bot.ban_chat_member(CHANNEL_ID, user_id)
        bot.unban_chat_member(CHANNEL_ID, user_id)
    except Exception as e:
        print("Ошибка удаления:", e)

# ====== ПОДПИСКА ======
def activate_subscription(user_id, username):
    conn, cursor = get_db()

    start_date = datetime.now()
    end_date = start_date + timedelta(days=25)

    cursor.execute("""
    INSERT OR REPLACE INTO users (user_id, username, start_date, end_date, status)
    VALUES (?, ?, ?, ?, ?)
    """, (
        user_id,
        username,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
        "active"
    ))

    conn.commit()
    conn.close()

def check_subscriptions():
    conn, cursor = get_db()
    cursor.execute("SELECT user_id, end_date, status FROM users")
    users = cursor.fetchall()

    today = datetime.now().date()

    for user_id, end_date, status in users:
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        days_left = (end - today).days

        if status == "active":

            # Напоминания
            if days_left == 5:
                bot.send_message(user_id, "⏰ Через 5 дней заканчивается подписка.")
            if days_left == 3:
                bot.send_message(user_id, "⏰ Через 3 дня заканчивается подписка.")
            if days_left == 1:
                bot.send_message(user_id, "⏰ Завтра заканчивается подписка.")

            # Подписка истекла
            if days_left < 0:
                cursor.execute(
                    "UPDATE users SET status='expired' WHERE user_id=?",
                    (user_id,)
                )

                remove_from_channel(user_id)

                bot.send_message(
                    user_id,
                    "❌ Подписка завершена.\nДоступ к каналу закрыт."
                )

    conn.commit()
    conn.close()

# ====== МЕНЮ ======
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💳 Премиум — 900₽ / 25 дней")
    kb.add("🔐 Закрытый канал")
    kb.add("📊 Мой статус")
    kb.add("ℹ️ О сервисе")
    return kb

# ====== ОБРАБОТЧИКИ ======
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "Привет 👋\n\n"
        "Премиум подписка: 900₽ / 25 дней\n\n"
        "Выбери действие 👇",
        reply_markup=main_menu()
    )

@bot.message_handler(commands=["testpay"])
def test_payment(message):
    user_id = message.from_user.id
    username = message.from_user.username

    activate_subscription(user_id, username)

    invite_link = create_invite_link()

    if invite_link:
        bot.send_message(
            message.chat.id,
            "✅ Подписка активирована!\n\n"
            f"🔐 Вход в канал:\n{invite_link}"
        )
    else:
        bot.send_message(message.chat.id, "Ошибка создания ссылки.")

@bot.message_handler(func=lambda m: m.text == "📊 Мой статус")
def status(message):
    conn, cursor = get_db()
    cursor.execute("SELECT end_date, status FROM users WHERE user_id=?",
                   (message.from_user.id,))
    user = cursor.fetchone()
    conn.close()

    if user:
        end_date, status = user
        bot.send_message(
            message.chat.id,
            f"📅 Подписка до: {end_date}\nСтатус: {status}"
        )
    else:
        bot.send_message(message.chat.id, "У вас нет активной подписки.")

@bot.message_handler(func=lambda m: m.text == "💳 Премиум — 900₽ / 25 дней")
def premium(message):
    pay_url = create_payment(message.from_user.id)

    bot.send_message(
        message.chat.id,
        f"💳 Оплатите подписку по ссылке:\n\n{pay_url}\n\n"
        "После оплаты доступ откроется автоматически."
    )


@bot.message_handler(func=lambda m: m.text == "🔐 Закрытый канал")
def channel_info(message):
    bot.send_message(
        message.chat.id,
        "Доступ открывается после активации подписки."
    )

@bot.message_handler(func=lambda m: m.text == "ℹ️ О сервисе")
def about(message):
    bot.send_message(
        message.chat.id,
        "Закрытый подписочный канал.\nДоступ только для активных подписчиков."
    )

@app.route("/yookassa", methods=["POST"])
def yookassa_webhook():
    data = request.json

    if data.get("event") == "payment.succeeded":
        payment = data["object"]
        user_id = payment["metadata"]["user_id"]

        activate_subscription(user_id, None)

        invite_link = create_invite_link()

        if invite_link:
            bot.send_message(
                user_id,
                f"✅ Оплата прошла успешно!\n\n🔐 Вход в канал:\n{invite_link}"
            )

    return "OK", 200


# ====== ФОН ======
def scheduler():
    while True:
        check_subscriptions()
        time.sleep(86400)

threading.Thread(target=scheduler, daemon=True).start()

# ====== ЗАПУСК ======
print("Бот запущен...")
def run_flask():
    app.run(port=5000)

threading.Thread(target=run_flask, daemon=True).start()

bot.polling(none_stop=True)

