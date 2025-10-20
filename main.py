from fastapi import FastAPI, Request, HTTPException
import httpx, os, time

app = FastAPI()

# Настройки бота
TG_TOKEN   = os.getenv("TG_TOKEN")           # Токен Telegram-бота
CHAT_ID    = os.getenv("TG_CHAT_ID")         # Твой ID (узнать у @userinfobot)
SECRET_KEY = os.getenv("SECRET_KEY", "charviz123")
SERVER_URL = os.getenv("SERVER_URL", "https://YOUR-RENDER-URL")  # заменишь позже своим URL

# Память для последнего сигнала
LAST_SIGNAL = {}
BASE_STAKE  = int(os.getenv("BASE_STAKE", "500"))
ENTRY_DELAY = int(os.getenv("ENTRY_DELAY", "20"))

# Функция для отправки сообщений в Telegram
async def send_tg(text, buttons: bool = True):
    if not TG_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }

    # Кнопки "Войти сейчас" и "Пропустить"
    if buttons:
        payload["reply_markup"] = {
            "inline_keyboard": [[
                {"text": "Войти сейчас", "url": f"{SERVER_URL}/enter?k={SECRET_KEY}"},
                {"text": "Пропустить", "url": f"{SERVER_URL}/skip?k={SECRET_KEY}"}
            ]]
        }

    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(url, json=payload)

# Основной вебхук — принимает сигнал с TradingView
@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
    except:
        raise HTTPException(400, "Invalid JSON")

    direction  = data.get("direction", "NONE")
    symbol     = data.get("symbol", "UNKNOWN")
    confidence = float(data.get("confidence", 0))
    expiry     = int(data.get("expiry_minutes", 5))

    # Если сигнал слабый — пропускаем
    if direction == "NONE" or confidence < 0.97:
        await send_tg("следующая", buttons=False)
        return {"ok": True, "skipped": True}

    # Сохраняем сигнал
    global LAST_SIGNAL
    LAST_SIGNAL = {
        "symbol": symbol,
        "direction": direction,
        "confidence": confidence,
        "expiry": expiry,
        "stake": BASE_STAKE,
        "ts": time.time(),
        "approved_at": None,
        "skipped_at": None,
    }

    # Отправляем сигнал в Telegram
    text = f"{direction} 5M ({int(confidence*100)}%) — {symbol}\nВход через: {ENTRY_DELAY} сек\nСтавка: {BASE_STAKE} ₸"
    await send_tg(text, buttons=True)
    return {"ok": True, "sent": True}

# Проверка статуса
@app.get("/status")
async def status():
    return {"ok": True, "signal": LAST_SIGNAL, "entry_delay": ENTRY_DELAY}

# Кнопка "Войти сейчас"
@app.get("/enter")
async def enter(k: str):
    if k != SECRET_KEY:
        raise HTTPException(403, "Forbidden")
    if not LAST_SIGNAL:
        return {"ok": False, "msg": "no_signal"}
    LAST_SIGNAL["approved_at"] = time.time()
    return {"ok": True, "approved_at": LAST_SIGNAL["approved_at"]}

# Кнопка "Пропустить"
@app.get("/skip")
async def skip(k: str):
    if k != SECRET_KEY:
        raise HTTPException(403, "Forbidden")
    if not LAST_SIGNAL:
        return {"ok": False, "msg": "no_signal"}
    LAST_SIGNAL["skipped_at"] = time.time()
    return {"ok": True, "skipped_at": LAST_SIGNAL["skipped_at"]}

# Главная страница (для проверки)
@app.get("/")
async def root():
    return {"ok": True, "message": "Charviz Precision Bot is running!"}
