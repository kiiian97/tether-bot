import os
import time
import requests
from flask import Flask, request

app = Flask(__name__)

# توکن رباتت رو از @BotFather بگیر و همینجا جایگزین کن
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8543390033:AAHRrBeTXagkSjJh9KOTXq0g68Wd8tDek08")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

MAX_RETRIES = 3
RETRY_DELAY = 1.5  # ثانیه
CACHE_TTL = 30  # ثانیه - مدت اعتبار قیمت ذخیره‌شده

_price_cache = {"price": None, "time": 0}


def get_usdt_price():
    """نرخ لحظه‌ای تتر به تومان را از نوبیتکس می‌گیرد (نرخ واقعی بازار آزاد)."""
    now = time.time()
    if _price_cache["price"] and (now - _price_cache["time"] < CACHE_TTL):
        return _price_cache["price"]

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                "https://api.nobitex.ir/market/stats",
                json={"srcCurrency": "usdt", "dstCurrency": "rls"},
                timeout=10,
            )
            print(f"NOBITEX STATUS: {resp.status_code}", flush=True)
            print(f"NOBITEX BODY: {resp.text[:500]}", flush=True)
            data = resp.json()
            rial_price = float(data["stats"]["usdt-rls"]["latest"])
            toman_price = rial_price / 10  # ریال به تومان
            _price_cache["price"] = toman_price
            _price_cache["time"] = now
            return toman_price
        except Exception as e:
            print(f"NOBITEX EXCEPTION: {type(e).__name__}: {e}", flush=True)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

    if _price_cache["price"]:
        return _price_cache["price"]
    return None


def send_message(chat_id, text, keyboard=None):
    payload = {"chat_id": chat_id, "text": text}
    if keyboard:
        payload["reply_markup"] = keyboard
    for attempt in range(MAX_RETRIES):
        try:
            requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)
            return
        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)


MAIN_KEYBOARD = {
    "keyboard": [
        [{"text": "💰 نرخ لحظه‌ای تتر"}],
        [{"text": "🧮 ماشین حساب تتر"}],
    ],
    "resize_keyboard": True,
}

user_state = {}


@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()

    if update and "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        if text == "/start":
            user_state.pop(chat_id, None)
            send_message(
                chat_id,
                "به ربات نرخ تتر خوش آمدید 👋\nیکی از گزینه‌های زیر را انتخاب کنید:",
                MAIN_KEYBOARD,
            )

        elif text == "💰 نرخ لحظه‌ای تتر":
            price = get_usdt_price()
            if price:
                send_message(chat_id, f"نرخ لحظه‌ای تتر: {price:,.0f} تومان", MAIN_KEYBOARD)
            else:
                send_message(chat_id, "خطا در دریافت قیمت. لطفاً دوباره تلاش کنید.", MAIN_KEYBOARD)

        elif text == "🧮 ماشین حساب تتر":
            user_state[chat_id] = "awaiting_amount"
            send_message(chat_id, "چند تتر می‌خواهید محاسبه کنید؟ عدد را ارسال کنید (مثلاً 10)", MAIN_KEYBOARD)

        elif user_state.get(chat_id) == "awaiting_amount":
            try:
                amount = float(text.replace(",", "").strip())
                price = get_usdt_price()
                if price:
                    total = amount * price
                    send_message(chat_id, f"{amount:g} تتر = {total:,.0f} تومان", MAIN_KEYBOARD)
                else:
                    send_message(chat_id, "خطا در دریافت قیمت. دوباره تلاش کنید.", MAIN_KEYBOARD)
            except ValueError:
                send_message(chat_id, "لطفاً فقط عدد ارسال کنید. مثلاً: 10", MAIN_KEYBOARD)
            user_state.pop(chat_id, None)

        else:
            send_message(chat_id, "از دکمه‌های پایین استفاده کنید 👇", MAIN_KEYBOARD)

    return "ok"


@app.route("/")
def index():
    return "Bot is running."


@app.route("/debug")
def debug():
    results = []
    tests = [
        ("Nobitex", "https://api.nobitex.ir/market/stats"),
        ("BrsApi", "https://Api.BrsApi.ir/Market/Gold_Currency_Pro.php?key=FreeSV0E1LSgB9RDjuf0QorSLViX8pPG&section=cryptocurrency"),
        ("AlanChand", "https://alanchand.com/api/currency/tether"),
        ("CoinGecko-USD", "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=usd"),
        ("Wallex", "https://api.wallex.ir/v1/markets"),
    ]
    for name, url in tests:
        try:
            r = requests.get(url, timeout=8)
            results.append(f"{name}: STATUS {r.status_code} | {r.text[:150]}")
        except Exception as e:
            results.append(f"{name}: EXCEPTION {type(e).__name__}: {e}")
    return "<br><br>".join(results)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
