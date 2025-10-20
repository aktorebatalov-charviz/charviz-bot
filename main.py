from fastapi import FastAPI, Request, HTTPException
import httpx, os, time, logging

# ----------------- НАСТРОЙКА ЛОГГЕРА -----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("charviz")

app = FastAPI()

# ----------------- ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ -----------------
TG_TOKEN   = os.getenv("TG_TOKEN", "")
CHAT_ID    = os.getenv("TG_CHAT_ID", "")
SECRET_KEY = os.getenv("SECRET_KEY", "charviz123")
SERVER_URL = os.getenv("SERVER_URL", "")  # пример: https://charviz-bot.onrender.com

BASE_STAKE  = int(os.getenv("BASE_STAKE", "500"))
ENTRY_DELAY = int(os.getenv("ENTRY_DELAY", "20"))

# Память последнего сигнала
LAST_SIGNAL = {}

# ----------------- ВСПОМОГАТЕЛЬНОЕ -----------------
async def send_tg(text: str, buttons: bool = False):
    """
    Отправка сообщения в Telegram. По умолчанию БЕЗ кнопок,
    чтобы ничего не ломалось даже если SERVER_URL не задан.
    """
    if not TG_TOKEN or not CHAT_ID:
        log.error("TG creds missing: TG_TOKEN or TG_CHAT_ID пустые")
        return

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }

    # Кнопки включаем только если SERVER_URL корректен
    valid_url = SERVER_URL.startswith("https://") and "YOUR-RENDER-URL" not in SERVER_URL
    if buttons and valid_url:
        payload["reply_markup"] = {
            "inline_keyboard": [[
                {"text": "Войти сейчас", "url": f"{SERVER_URL}/enter?k={SECRET_KEY}"},
                {"text": "Пропустить",    "url": f"{SERVER_URL}/skip?k={SECRET_KEY}"}
            ]]
        }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json=payload)
            if r.status_code != 200:
                log.error("TG send error: %s %s", r.status_code, r.text)
    except Exception as e:
        log.exception("TG send exception: %s", e)

# ----------------- РОУТЫ -----------------
@app.get("/")
async def root():
    return {"ok": True, "message": "Charviz Precision Bot is running!"}

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/status")
async def status():
    return {"ok": True, "signal": LAST_SIGNAL, "entry_delay": ENTRY_DELAY}

@app.get("/test")
async def test():
    await send_tg("✅ Тест: бот на связи.")
    return {"ok": True}

# Основной вебхук — принимает сигнал с TradingView
@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        print("=== RECEIVED WEBHOOK ===")   # виден в Logs на Render
        print(data)                        # сырой JSON для диагностики
        log.info("Webhook payload: %s", data)
    except Exception:
        raise HTTPException(400, "Invalid JSON")

    direction  = data.get("direction", "NONE")
    symbol     = data.get("symbol", "UNKNOWN")
    confidence = float(data.get("confidence", 0))
    expiry     = int(data.get("expiry_minutes", 5))

    # Порог на время тестов 0.90 — чтобы сигналы шли чаще.
    # Когда убедимся, что всё ок — вернём на 0.97.
    if direction == "NONE" or confidence < 0.90:
        await send_tg("следующая", buttons=False)
        return {"ok": True, "skipped": True}

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

    text = f"{direction} 5M ({int(confidence*100)}%) — {symbol}\nВход через: {ENTRY_DELAY} сек\nСтавка: {BASE_STAKE} ₸"
    await send_tg(text, buttons=False)  # кнопки выключены по умолчанию
    return {"ok": True, "sent": True}

# Эти два эндпоинта оставил — пригодятся позже, когда вернём кнопки
@app.get("/enter")
async def enter(k: str):
    if k != SECRET_KEY:
        raise HTTPException(403, "Forbidden")
    if not LAST_SIGNAL:
        return {"ok": False, "msg": "no_signal"}
    LAST_SIGNAL["approved_at"] = time.time()
    return {"ok": True, "approved_at": LAST_SIGNAL["approved_at"]}

@app.get("/skip")
async def skip(k: str):
    if k != SECRET_KEY:
        raise HTTPException(403, "Forbidden")
    if not LAST_SIGNAL:
        return {"ok": False, "msg": "no_signal"}
    LAST_SIGNAL["skipped_at"] = time.time()
    return {"ok": True, "skipped_at": LAST_SIGNAL["skipped_at"]}
